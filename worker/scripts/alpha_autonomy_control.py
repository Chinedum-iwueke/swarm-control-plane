#!/usr/bin/env python3
"""Synchronize audited control-plane pause state into VM1 native research."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time

import httpx


SCHEMA_VERSION = "alpha-autonomy-drain-v1.0.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        os.chmod(temporary, 0o600)
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def drain_document(scopes: list[dict]) -> dict:
    global_scope = next(
        (
            scope
            for scope in scopes
            if scope.get("scope_type") == "global"
            and scope.get("scope_key") == "all"
        ),
        None,
    )
    paused = bool(global_scope and global_scope.get("is_paused"))
    return {
        "schema_version": SCHEMA_VERSION,
        "paused": paused,
        "mode": "drain" if paused else "active",
        "reason": (
            global_scope.get("reason")
            if global_scope
            else "No audited global pause is active."
        ),
        "control_updated_at": (
            global_scope.get("updated_at") if global_scope else None
        ),
        "synchronized_at": utc_now(),
        "new_control_plane_leases_blocked": paused,
        "new_native_jobs_blocked": paused,
        "running_work_allowed_to_finish": True,
    }


def client() -> httpx.Client:
    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not api_url or not token:
        raise RuntimeError("Protected operator environment is required.")
    return httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )


def project_pause_marker(marker_path: Path, *, paused: bool) -> None:
    marker_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if paused:
        marker_path.touch(mode=0o600, exist_ok=True)
        os.chmod(marker_path, 0o600)
    else:
        marker_path.unlink(missing_ok=True)


def synchronize(
    http: httpx.Client, state_path: Path, marker_path: Path | None = None
) -> dict:
    response = http.get("/v1/control/scopes")
    response.raise_for_status()
    document = drain_document(response.json())
    atomic_json(state_path, document)
    if marker_path is not None:
        project_pause_marker(marker_path, paused=document["paused"])
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("watch", "sync", "status", "pause", "resume"))
    parser.add_argument(
        "--state",
        type=Path,
        default=Path("/home/omenka/.local/state/invariance-swarm/alpha-autonomy-drain.json"),
    )
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument(
        "--marker",
        type=Path,
        default=Path("/home/omenka/.local/state/invariance-swarm/alpha-autonomy.paused"),
    )
    parser.add_argument("--reason")
    parser.add_argument("--actor", default="founder-operator")
    args = parser.parse_args()

    if args.action == "status":
        if not args.state.exists():
            print(json.dumps({"paused": True, "state": "unavailable_fail_closed"}))
            return 1
        print(args.state.read_text(encoding="utf-8"), end="")
        return 0

    with client() as http:
        if args.action in {"pause", "resume"}:
            if not args.reason or len(args.reason.strip()) < 10:
                parser.error("pause/resume require --reason with at least 10 characters")
            response = http.post(
                f"/v1/control/{args.action}",
                json={
                    "scope_type": "global",
                    "scope_key": "all",
                    "reason": args.reason.strip(),
                    "actor": args.actor,
                },
            )
            response.raise_for_status()

        if args.action != "watch":
            print(
                json.dumps(
                    synchronize(http, args.state, args.marker),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        while True:
            try:
                document = synchronize(http, args.state, args.marker)
                print(
                    json.dumps(
                        {
                            "event": "alpha_autonomy_control_synchronized",
                            "paused": document["paused"],
                            "mode": document["mode"],
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
            except Exception as exc:
                # Retain last-known state. Native readers fail closed if no valid
                # state has ever been synchronized.
                print(
                    json.dumps(
                        {
                            "event": "alpha_autonomy_control_sync_failed",
                            "error": type(exc).__name__,
                            "last_known_state_retained": args.state.exists(),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
            time.sleep(max(1.0, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
