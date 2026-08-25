#!/usr/bin/env python3
import hashlib
import json
import os
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

import httpx

SUBJECT_TYPE = "research-candidate"
SUBJECT_ID = "gov002-orthogonality-pilot-v1"


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def main() -> int:
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    subject_digest = sha(SUBJECT_ID)
    evidence_digest = sha("gov002-pilot-evidence")
    with httpx.Client(base_url=base, headers=headers, timeout=30) as client:
        created = client.post(
            "/v1/lifecycles/subjects",
            json={
                "subject_type": SUBJECT_TYPE,
                "subject_id": SUBJECT_ID,
                "subject_digest": subject_digest,
            },
        )
        created.raise_for_status()
        dossier = created.json()
        desired = [
            ("research", "proposed", "register", "registered", None),
            ("research", "registered", "start", "running", None),
            ("research", "running", "succeed", "succeeded", None),
            (
                "evidence",
                "unassessed",
                "admit",
                "admissible",
                "research-execution-agent",
            ),
        ]
        for dimension, prior, command, resulting, originator in desired:
            projection = next(
                item
                for item in dossier["projections"]
                if item["dimension"] == dimension
            )
            if projection["state"] == resulting:
                continue
            if projection["state"] != prior:
                raise RuntimeError(
                    f"Unexpected {dimension} state {projection['state']}; expected {prior}."
                )
            command_id = uuid5(
                NAMESPACE_URL, f"gov002:{SUBJECT_ID}:{dimension}:{command}"
            )
            response = client.post(
                f"/v1/lifecycles/subjects/{SUBJECT_TYPE}/{SUBJECT_ID}/transitions",
                json={
                    "command_id": str(command_id),
                    "actor": "founder-operator",
                    "dimension": dimension,
                    "command": command,
                    "expected_version": projection["version"],
                    "subject_digest": subject_digest,
                    "evidence": [evidence_digest],
                    "reason": f"Execute the bounded GOV-002 {dimension} {command} pilot transition.",
                    "risk_level": 1,
                    "environment": "internal",
                    "requester": "gov002-pilot",
                    "originator": originator,
                    "effective_at": datetime.now(UTC).isoformat(),
                },
            )
            response.raise_for_status()
            dossier = response.json()

        states = {item["dimension"]: item["state"] for item in dossier["projections"]}
        assert states["research"] == "succeeded"
        assert states["evidence"] == "admissible"
        assert states["operations"] in {"not-considered", "candidate"}
        assert states["capital"] == "no-authority"
        operation = next(
            item for item in dossier["projections"] if item["dimension"] == "operations"
        )
        if operation["state"] == "candidate":
            nominated_dossier = dossier
        else:
            if operation["state"] != "not-considered":
                raise RuntimeError(f"Unexpected operations state {operation['state']}.")
            nominated = client.post(
                f"/v1/lifecycles/subjects/{SUBJECT_TYPE}/{SUBJECT_ID}/transitions",
                json={
                    "command_id": str(
                        uuid5(
                            NAMESPACE_URL,
                            f"gov002:{SUBJECT_ID}:operations:nominate",
                        )
                    ),
                    "actor": "founder-operator",
                    "dimension": "operations",
                    "command": "nominate",
                    "expected_version": operation["version"],
                    "subject_digest": subject_digest,
                    "evidence": [dossier["dossier_digest"]],
                    "reason": "Prove that operations changes only after a separate explicit command.",
                    "risk_level": 1,
                    "environment": "internal",
                    "requester": "gov002-pilot",
                    "originator": "research-execution-agent",
                    "effective_at": datetime.now(UTC).isoformat(),
                },
            )
            nominated.raise_for_status()
            nominated_dossier = nominated.json()
        final = nominated_dossier
        final_states = {
            item["dimension"]: item["state"] for item in final["projections"]
        }
        nomination_event = next(
            item
            for item in final["events"]
            if item["dimension"] == "operations" and item["command"] == "nominate"
        )
        assert nomination_event["prior_state"] == "not-considered"
        assert final_states["operations"] == "candidate"
        assert final_states["capital"] == "no-authority"
        print(
            json.dumps(
                {
                    "success": True,
                    "subject": f"{SUBJECT_TYPE}:{SUBJECT_ID}",
                    "subject_digest": subject_digest,
                    "states_before_explicit_operations_command": {
                        **states,
                        "operations": nomination_event["prior_state"],
                    },
                    "states_after_explicit_operations_command": final_states,
                    "event_count": len(final["events"]),
                    "dossier_digest": final["dossier_digest"],
                    "capital_or_order_authority": False,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
