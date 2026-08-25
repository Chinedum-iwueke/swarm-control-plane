#!/usr/bin/env python3
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

import httpx

SUBJECT_TYPE = "research-candidate"
SUBJECT_ID = "gov003-consequence-pilot-v1"


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def main():
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    digest = sha(SUBJECT_ID)
    evidence = sha("gov003-live-evidence")
    with httpx.Client(base_url=base, headers=headers, timeout=30) as client:
        created = client.post(
            "/v1/lifecycles/subjects",
            json={
                "subject_type": SUBJECT_TYPE,
                "subject_id": SUBJECT_ID,
                "subject_digest": digest,
            },
        )
        created.raise_for_status()
        dossier = created.json()
        for dimension, prior, command, resulting, originator in [
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
            (
                "operations",
                "not-considered",
                "nominate",
                "candidate",
                "research-execution-agent",
            ),
        ]:
            projection = next(
                x for x in dossier["projections"] if x["dimension"] == dimension
            )
            if projection["state"] == resulting:
                continue
            if projection["state"] != prior:
                raise RuntimeError(
                    f"Unexpected {dimension} state {projection['state']}"
                )
            response = client.post(
                f"/v1/lifecycles/subjects/{SUBJECT_TYPE}/{SUBJECT_ID}/transitions",
                json={
                    "command_id": str(
                        uuid5(NAMESPACE_URL, f"gov003:setup:{dimension}:{command}")
                    ),
                    "actor": "founder-operator",
                    "dimension": dimension,
                    "command": command,
                    "expected_version": projection["version"],
                    "subject_digest": digest,
                    "evidence": [evidence],
                    "reason": f"Prepare the bounded GOV-003 {dimension} pilot state.",
                    "risk_level": 1,
                    "environment": "internal",
                    "requester": "gov003-pilot",
                    "originator": originator,
                    "effective_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            response.raise_for_status()
            dossier = response.json()

        consequences = []
        for index, (dimension, action, expected_prior) in enumerate(
            [
                ("operations", "promote", "candidate"),
                ("evidence", "quarantine", "admissible"),
                ("evidence", "reinstate", "disputed"),
                ("operations", "retire", "candidate"),
                ("operations", "reinstate", "retired"),
            ]
        ):
            dossier = client.get(
                f"/v1/lifecycles/subjects/{SUBJECT_TYPE}/{SUBJECT_ID}"
            ).json()
            projection = next(
                x for x in dossier["projections"] if x["dimension"] == dimension
            )
            if index == 1:
                promoted = consequences[0]
                operations = next(
                    x for x in dossier["projections"] if x["dimension"] == "operations"
                )
                reversed_result = client.post(
                    f"/v1/lifecycle-consequences/{promoted['id']}/reverse",
                    json={
                        "command_id": str(
                            uuid5(NAMESPACE_URL, "gov003:reverse:promotion")
                        ),
                        "actor": "founder-operator",
                        "expected_version": operations["version"],
                        "reason": "Reverse the bounded promotion and restore its exact prior state.",
                        "risk_level": 1,
                        "environment": "internal",
                        "originator": "research-execution-agent",
                        "evaluator": "risk-reviewer",
                    },
                )
                reversed_result.raise_for_status()
                consequences.append(reversed_result.json())
                dossier = client.get(
                    f"/v1/lifecycles/subjects/{SUBJECT_TYPE}/{SUBJECT_ID}"
                ).json()
                projection = next(
                    x for x in dossier["projections"] if x["dimension"] == dimension
                )
            if projection["state"] != expected_prior:
                raise RuntimeError(
                    f"Unexpected {dimension} state {projection['state']}; expected {expected_prior}"
                )
            now = datetime.now(timezone.utc)
            result = client.post(
                f"/v1/lifecycle-consequences/subjects/{SUBJECT_TYPE}/{SUBJECT_ID}",
                json={
                    "command_id": str(
                        uuid5(NAMESPACE_URL, f"gov003:{dimension}:{action}")
                    ),
                    "actor": "founder-operator",
                    "action": action,
                    "dimension": dimension,
                    "expected_version": projection["version"],
                    "subject_digest": digest,
                    "evidence": [evidence],
                    "evidence_epoch": now.isoformat(),
                    "approvers": ["founder-operator", "risk-reviewer"],
                    "affected_descendants": ["pilot-descendant:one"],
                    "expires_at": (now + timedelta(days=7)).isoformat(),
                    "reason": f"Exercise the bounded GOV-003 {action} consequence with retained rollback.",
                    "risk_level": 1,
                    "environment": "internal",
                    "originator": "research-execution-agent",
                    "evaluator": "risk-reviewer",
                },
            )
            result.raise_for_status()
            consequences.append(result.json())
        final = client.get(f"/v1/lifecycles/subjects/{SUBJECT_TYPE}/{SUBJECT_ID}")
        final.raise_for_status()
        states = {x["dimension"]: x["state"] for x in final.json()["projections"]}
        assert states == {
            "capital": "no-authority",
            "evidence": "admissible",
            "operations": "candidate",
            "research": "succeeded",
        }
        print(
            json.dumps(
                {
                    "success": True,
                    "subject_digest": digest,
                    "states": states,
                    "consequence_count": len(consequences),
                    "consequence_digests": [x["record_digest"] for x in consequences],
                    "dossier_digest": final.json()["dossier_digest"],
                    "capital_or_order_authority": False,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
