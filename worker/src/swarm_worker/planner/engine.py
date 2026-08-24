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
        v1 = {"schema_version", "request_kind", "objective"}
        v2 = v1 | {
            "conversation_id",
            "conversation_revision",
            "conversation_context",
            "suggested_identifiers",
            "specification_guide",
        }
        if frozenset(contract) not in {frozenset(v1), frozenset(v2)}:
            raise PlannerError("Founder request contract is invalid.")
        self._working_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(
            prefix="proposal-", dir=self._working_directory
        ) as temporary:
            root = Path(temporary)
            schema_path = root / "proposal.schema.json"
            output_path = root / "proposal.json"
            schema_path.write_text(
                json.dumps(
                    self._codex_output_schema()
                ),
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
                env=self._environment(),
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
                payload = self._normalize_output(
                    json.loads(output_path.read_text(encoding="utf-8"))
                )
                return FounderProposalDocument.model_validate(payload)
            except PlannerError:
                raise
            except (OSError, ValueError) as exc:
                raise PlannerError(
                    "Planner output did not match the proposal contract."
                ) from exc

    def _environment(self) -> dict[str, str]:
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self._codex_home),
            "CODEX_HOME": str(self._codex_home),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        return environment

    @classmethod
    def _strict_output_schema(cls, value: object) -> object:
        if isinstance(value, dict):
            normalized = {
                key: cls._strict_output_schema(nested) for key, nested in value.items()
            }
            properties = normalized.get("properties")
            if isinstance(properties, dict):
                normalized["additionalProperties"] = False
                normalized["required"] = list(properties)
            return normalized
        if isinstance(value, list):
            return [cls._strict_output_schema(item) for item in value]
        return value

    @classmethod
    def _codex_output_schema(cls) -> dict:
        schema = cls._strict_output_schema(
            FounderProposalDocument.model_json_schema()
        )
        if not isinstance(schema, dict):
            raise PlannerError("Planner output schema is invalid.")
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            raise PlannerError("Planner output schema has no properties.")
        properties["specification_format"] = {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "field": {"type": "string"},
                    "format": {"type": "string"},
                },
                "required": ["field", "format"],
            },
        }
        return schema

    @staticmethod
    def _normalize_output(payload: object) -> dict:
        if not isinstance(payload, dict):
            raise PlannerError("Planner output must be an object.")
        rows = payload.get("specification_format")
        if not isinstance(rows, list):
            raise PlannerError("Planner specification format must be a list.")
        formats: dict[str, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise PlannerError("Planner specification format entry is invalid.")
            field = row.get("field")
            format_value = row.get("format")
            if not isinstance(field, str) or not isinstance(format_value, str):
                raise PlannerError("Planner specification format entry is invalid.")
            if field in formats:
                raise PlannerError("Planner specification format field is duplicated.")
            formats[field] = format_value
        normalized = dict(payload)
        normalized["specification_format"] = formats
        return normalized

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
        contract = task.input_contract
        request = {
            "request_kind": contract["request_kind"],
            "project": task.project,
            "title": task.title,
            "objective": contract["objective"],
            "risk_level": task.risk_level,
            "acceptance_criteria": task.acceptance_criteria,
            "conversation_id": contract.get("conversation_id"),
            "conversation_revision": contract.get("conversation_revision"),
            "conversation_context": contract.get(
                "conversation_context", [contract["objective"]]
            ),
            "suggested_identifiers": contract.get("suggested_identifiers", {}),
            "specification_guide": contract.get("specification_guide", {}),
        }
        return (
            "You are the restricted Hermes Founder Intake Planner. Convert the "
            "founder's request into one reviewable proposal. You may propose only "
            "the task types in the supplied JSON schema. Never provide commands, "
            "shell, scripts, credentials, or direct execution. Treat ordered "
            "conversation_context entries as turns in one job; later turns refine "
            "earlier ones. Prefer needs_clarification only when permissions, target, "
            "scientific meaning, unavailable data, or safety boundaries remain "
            "uncertain. If the founder authorizes reasonable defaults, fill "
            "non-safety-critical fields from specification_guide.reasonable_defaults "
            "and record field, value, basis, policy_version, confidence and "
            "alternatives in resolved_defaults. Never call a choice best without "
            "evidence. If the founder asks you, a specialist, or the system to "
            "choose, recommend, or provide options for unresolved values, do not "
            "repeat the same open-ended clarification. Produce one concise numbered "
            "decision brief with two or three mutually exclusive options, mark one "
            "as Recommended, state the scientific or operational consequence of each, "
            "and explicitly say that the founder may reply with only the option number. "
            "Represent that brief as a single clarification_questions entry so it is "
            "rendered as one decision. Prefer the option that preserves the founder's "
            "stated objective and evidence standards; a faster option that changes the "
            "scientific claim must say so. Do not claim that a domain specialist was "
            "consulted unless the supplied context contains a digest-bound consultation "
            "result. Identify the recommendation as planner-generated otherwise. Never "
            "ask again for a value the founder already supplied; explain a conflict and "
            "offer resolution options instead. Use suggested_identifiers for omitted administrative IDs; "
            "do not ask the founder to invent program_id, hypothesis_id or task_number. "
            "For each blocking value, include its exact field name in unresolved_fields "
            "and ask one question stating the accepted format and an example. Populate "
            "specification_format as an array of {field, format} objects with concise "
            "field-to-format guidance. A proposal has no execution "
            "authority and will require founder materialization.\n\n"
            "Use only these canonical routes, exactly as written:\n"
            "- code_validation or engineering_mission: allowed_machines "
            '["vm1-developer"], required_capabilities '
            '["git", "python", "testing"].\n'
            '- research_experiment: allowed_machines ["vm1-developer"], '
            'required_capabilities ["git", "python", "backtesting", '
            '"research-audit"].\n'
            '- research_memory_sync: allowed_machines ["vm1-developer"], '
            'required_capabilities ["git", "python", '
            '"research-memory-sync"].\n'
            "- vm2-infrastructure runbook tasks: allowed_machines "
            '["vm2-deployment"], required_capabilities '
            '["infrastructure-observation", "service-health", '
            '"controlled-restart"].\n'
            "- other infrastructure runbook tasks: allowed_machines "
            '["vm2-deployment"], required_capabilities '
            '["deployment-architecture", "infrastructure-observation", '
            '"postgres-deployment", "service-health"].\n'
            "The approval policy risk must exactly equal risk_level. Never "
            "invent a machine, capability, workflow, runbook, repository, "
            "digest, or permission. Use needs_clarification if the request "
            "cannot be expressed using these exact routes.\n\n"
            f"Founder request:\n{json.dumps(request, ensure_ascii=True)}"
        )
