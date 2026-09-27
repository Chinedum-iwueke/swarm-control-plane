from __future__ import annotations

import argparse
import json
import os
import re
import select
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

DEVICE_CODE = re.compile(r"\b[A-Z0-9]{4,6}-[A-Z0-9]{4,6}\b")
DEVICE_URI = re.compile(r"https://auth\.openai\.com/codex/device")
AUTH_FAILURES = (
    "401 unauthorized",
    "incorrect api key",
    "authentication required",
    "not logged in",
    "refresh token",
    "please run codex login",
)


@dataclass(frozen=True)
class ProbeResult:
    healthy: bool
    authentication_failed: bool
    summary: str


class RecoveryClient:
    def __init__(self, api_url: str, token: str) -> None:
        self._client = httpx.Client(
            base_url=api_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

    def close(self) -> None:
        self._client.close()

    def current(self, runtime_key: str) -> dict[str, Any] | None:
        response = self._client.get(
            "/v1/codex-auth/recoveries", params={"runtime_key": runtime_key}
        )
        response.raise_for_status()
        values = response.json()
        return values[0] if values else None

    def report(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            "/v1/codex-auth/recoveries/report", json=payload
        )
        response.raise_for_status()
        return response.json()


class CodexRuntime:
    def __init__(self, binary: Path, codex_home: Path, model: str) -> None:
        self.binary = binary
        self.codex_home = codex_home
        self.model = model
        self.lock = codex_home / "credential-refresh.lock"

    def environment(self) -> dict[str, str]:
        return {
            **os.environ,
            "CODEX_HOME": str(self.codex_home),
            "HOME": "/home/omenka",
            "NODE_OPTIONS": "--jitless",
        }

    def probe(self) -> ProbeResult:
        status = subprocess.run(
            [str(self.binary), "login", "status"],
            env=self.environment(),
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        status_output = f"{status.stdout}\n{status.stderr}".lower()
        if status.returncode != 0:
            return ProbeResult(False, True, _safe_summary(status_output))
        self.lock.touch(mode=0o600, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.codex_home) as directory:
            result_path = Path(directory) / "probe.txt"
            result = subprocess.run(
                [
                    "/usr/bin/flock",
                    "-x",
                    str(self.lock),
                    str(self.binary),
                    "exec",
                    "--ignore-user-config",
                    "--ephemeral",
                    "--sandbox",
                    "read-only",
                    "--model",
                    self.model,
                    "--output-last-message",
                    str(result_path),
                    "Return exactly: alpha-auth-probe-ok",
                ],
                env=self.environment(),
                text=True,
                capture_output=True,
                timeout=180,
                check=False,
            )
            output = f"{result.stdout}\n{result.stderr}".lower()
            exact = result_path.exists() and result_path.read_text().strip() == "alpha-auth-probe-ok"
            if result.returncode == 0 and exact:
                return ProbeResult(True, False, "real Codex probe succeeded")
            auth_failed = any(marker in output for marker in AUTH_FAILURES)
            return ProbeResult(False, auth_failed, _safe_summary(output))

    def begin_device_login(self) -> subprocess.Popen[str]:
        self.lock.touch(mode=0o600, exist_ok=True)
        return subprocess.Popen(
            [
                "/usr/bin/flock",
                "-x",
                str(self.lock),
                str(self.binary),
                "login",
                "--device-auth",
            ],
            env=self.environment(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )


class CodexAuthWatcher:
    def __init__(
        self,
        client: RecoveryClient,
        runtime: CodexRuntime,
        *,
        runtime_key: str,
        probe_interval_seconds: int = 600,
        poll_seconds: int = 5,
        code_ttl_seconds: int = 900,
    ) -> None:
        self.client = client
        self.runtime = runtime
        self.runtime_key = runtime_key
        self.probe_interval_seconds = probe_interval_seconds
        self.poll_seconds = poll_seconds
        self.code_ttl_seconds = code_ttl_seconds
        self.stopping = False

    def stop(self, *_: object) -> None:
        self.stopping = True

    def run(self, *, once: bool = False) -> int:
        while not self.stopping:
            current = self.client.current(self.runtime_key)
            if current and current["state"] == "expired":
                if not _retry_pending(current):
                    if once:
                        return 2
                    time.sleep(self.poll_seconds)
                    continue
                outcome = self._device_login(int(current["generation"]) + 1)
            else:
                probe = self.runtime.probe()
                generation = int(current["generation"]) if current else 0
                if probe.healthy:
                    self._report("healthy", generation, failure_summary=None)
                    if once:
                        return 0
                    time.sleep(self.probe_interval_seconds)
                    continue
                if not probe.authentication_failed:
                    self._report("error", generation, failure_summary=probe.summary)
                    if once:
                        return 3
                    time.sleep(self.probe_interval_seconds)
                    continue
                self._report(
                    "authentication_required",
                    generation,
                    failure_summary="Codex rejected the shared runtime credential.",
                )
                outcome = self._device_login(generation + 1)
            if once:
                return 0 if outcome == "healthy" else 2
        return 0

    def _device_login(self, generation: int) -> str:
        process = self.runtime.begin_device_login()
        uri: str | None = None
        code: str | None = None
        output: list[str] = []
        announced_at: datetime | None = None
        try:
            while not self.stopping:
                if process.stdout is not None:
                    ready, _, _ = select.select([process.stdout], [], [], self.poll_seconds)
                    if ready:
                        line = process.stdout.readline()
                        if line:
                            output.append(line)
                            if DEVICE_URI.search(line):
                                uri = DEVICE_URI.search(line).group(0)
                            match = DEVICE_CODE.search(line)
                            if match:
                                code = match.group(0)
                if uri and code and announced_at is None:
                    announced_at = datetime.now(UTC)
                    self._report(
                        "awaiting_authorization",
                        generation,
                        verification_uri=uri,
                        device_code=code,
                        code_expires_at=announced_at
                        + timedelta(seconds=self.code_ttl_seconds),
                        failure_summary="Founder device authorization is required.",
                    )
                if announced_at is not None:
                    current = self.client.current(self.runtime_key)
                    if current and _retry_pending(current):
                        return "retry"
                    if datetime.now(UTC) >= announced_at + timedelta(
                        seconds=self.code_ttl_seconds
                    ):
                        self._report(
                            "expired",
                            generation,
                            failure_summary="The 15-minute device code expired.",
                        )
                        return "expired"
                return_code = process.poll()
                if return_code is not None:
                    if return_code == 0 and self.runtime.probe().healthy:
                        self._report("healthy", generation, failure_summary=None)
                        return "healthy"
                    summary = _safe_summary("".join(output))
                    self._report("error", generation, failure_summary=summary)
                    return "error"
            return "stopped"
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

    def _report(self, state: str, generation: int, **values: Any) -> dict[str, Any]:
        payload = {
            "runtime_key": self.runtime_key,
            "state": state,
            "generation": generation,
            "verification_uri": values.get("verification_uri"),
            "device_code": values.get("device_code"),
            "code_expires_at": (
                values["code_expires_at"].isoformat()
                if values.get("code_expires_at")
                else None
            ),
            "failure_summary": values.get("failure_summary"),
        }
        result = self.client.report(payload)
        print(
            json.dumps(
                {
                    "event": "codex_auth_state_reported",
                    "runtime_key": self.runtime_key,
                    "state": state,
                    "generation": generation,
                }
            ),
            flush=True,
        )
        return result


def _retry_pending(value: dict[str, Any]) -> bool:
    requested = value.get("retry_requested_at")
    acknowledged = value.get("retry_acknowledged_at")
    return bool(requested and (not acknowledged or acknowledged < requested))


def _safe_summary(value: str) -> str:
    cleaned = " ".join(value.split())
    cleaned = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[redacted-credential]", cleaned)
    cleaned = re.sub(
        r"\beyJ[A-Za-z0-9_.-]{20,}", "[redacted-credential]", cleaned
    )
    for marker in ("access_token", "refresh_token", "id_token"):
        cleaned = cleaned.replace(marker, "[redacted-token-field]")
    return (cleaned or "Codex command failed without diagnostic output.")[:500]


def _read_token(path: Path | None) -> str:
    if path is not None:
        return path.read_text(encoding="utf-8").strip()
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Codex auth watcher orchestrator token is unavailable.")
    return token


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default=os.environ.get("SWARM_API_URL"))
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--runtime-key", default="vm1-shared-alpha-codex")
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path("/var/lib/invariance-swarm/codex-discovery-runtime"),
    )
    parser.add_argument("--codex-binary", type=Path, default=Path("/usr/bin/codex"))
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--probe-interval-seconds", type=int, default=600)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not args.api_url:
        raise RuntimeError("SWARM_API_URL is required.")
    client = RecoveryClient(args.api_url, _read_token(args.token_file))
    watcher = CodexAuthWatcher(
        client,
        CodexRuntime(args.codex_binary, args.codex_home, args.model),
        runtime_key=args.runtime_key,
        probe_interval_seconds=max(60, args.probe_interval_seconds),
    )
    signal.signal(signal.SIGTERM, watcher.stop)
    signal.signal(signal.SIGINT, watcher.stop)
    try:
        return watcher.run(once=args.once)
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
