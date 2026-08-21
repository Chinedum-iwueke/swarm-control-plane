from __future__ import annotations

import asyncio
import json
import os
import signal
import tempfile
from pathlib import Path

from swarm_worker.models import FounderProposalDocument, Task


class PlannerError(Exception):
    """A safe planner failure."""


class CodexProposalPlanner:
    def __init__(
        self,
        *,
        codex_binary: Path,
        codex_home: Path,
        model: str,
        timeout_seconds: float,
        working_directory: Path,
    ) -> None:
        self._binary = codex_binary
        self._codex_home = codex_home
        self._model = model
        self._timeout = timeout_seconds
        self._working_directory = working_directory

    async def plan(self, task: Task) -> FounderProposalDocument:
        if task.task_type != "founder_request":
            raise PlannerError("Planner only accepts founder_request tasks.")
        contract = task.input_contract
        if set(contract) != {"schema_version", "request_kind", "objective"}:
            raise PlannerError("Founder request contract is invalid.")
        self._working_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(
            prefix="proposal-", dir=self._working_directory
        ) as temporary:
            root = Path(temporary)
            codex_home = root / "codex-home"
            codex_home.mkdir(mode=0o700)
            (codex_home / "auth.json").symlink_to(self._codex_home / "auth.json")
            schema_path = root / "proposal.schema.json"
            output_path = root / "proposal.json"
            schema_path.write_text(
                json.dumps(FounderProposalDocument.model_json_schema()),
                encoding="utf-8",
            )
            command = [
                str(self._binary),
                "exec",
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--ignore-user-config",
                "--skip-git-repo-check",
                "--model",
                self._model,
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-C",
                str(root),
                "-",
            ]
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._environment(codex_home),
                start_new_session=True,
            )
            try:
                _, stderr = await asyncio.wait_for(
                    process.communicate(self._prompt(task).encode()),
                    timeout=self._timeout,
                )
            except TimeoutError as exc:
                await self._terminate(process)
                raise PlannerError("Founder proposal generation timed out.") from exc
            except asyncio.CancelledError:
                await self._terminate(process)
                raise
            if process.returncode != 0:
                detail = stderr.decode(errors="replace")[-500:]
                raise PlannerError(f"Founder proposal generation failed: {detail}")
            try:
                return FounderProposalDocument.model_validate_json(
                    output_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError) as exc:
                raise PlannerError(
                    "Planner output did not match the proposal contract."
                ) from exc

    def _environment(self, codex_home: Path | None = None) -> dict[str, str]:
        runtime_home = codex_home or self._codex_home
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(runtime_home),
            "CODEX_HOME": str(runtime_home),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        return environment

    @staticmethod
    async def _terminate(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            await asyncio.wait_for(process.wait(), timeout=5)
        except ProcessLookupError:
            return
        except TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
            await process.wait()

    @staticmethod
    def _prompt(task: Task) -> str:
        request = {
            "request_kind": task.input_contract["request_kind"],
            "project": task.project,
            "title": task.title,
            "objective": task.input_contract["objective"],
            "risk_level": task.risk_level,
            "acceptance_criteria": task.acceptance_criteria,
        }
        return (
            "You are the restricted Hermes Founder Intake Planner. Convert the "
            "founder's request into one reviewable proposal. You may propose only "
            "the task types in the supplied JSON schema. Never provide commands, "
            "shell, scripts, credentials, or direct execution. Prefer "
            "needs_clarification when permissions, target, acceptance criteria, "
            "or safety boundaries are uncertain. A proposal has no execution "
            "authority and will require founder materialization.\n\n"
            f"Founder request:\n{json.dumps(request, ensure_ascii=True)}"
        )
