#!/usr/bin/env python3
import hashlib
import json
import os

import httpx


def digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_manifest() -> dict:
    return {
        "schema_version": "authority-policy-v1.0.0",
        "policy_key": "invariance-institutional-authority",
        "version": "1.0.1",
        "roles": [
            {"role": role, "actors": ["founder-operator"]}
            for role in (
                "founder",
                "governance",
                "research",
                "engineering",
                "production",
                "risk",
                "security",
                "knowledge",
            )
        ],
        "identity_aliases": {
            "founder-mission-control": "founder-operator",
            "founder-telegram": "founder-operator",
        },
        "decisions": [
            {
                "decision_type": "policy-activation",
                "actions": ["activate"],
                "accountable_roles": ["governance"],
                "veto_roles": ["risk", "security"],
                "environments": ["internal"],
                "maximum_risk": 3,
                "delegable": False,
                "constitutional": True,
                "separation": [],
            },
            {
                "decision_type": "task-approval",
                "actions": ["approve", "reject", "revoke"],
                "accountable_roles": ["founder", "governance"],
                "veto_roles": ["risk", "security"],
                "environments": ["*"],
                "maximum_risk": 3,
                "delegable": True,
                "constitutional": False,
                "separation": [
                    {
                        "field": "requester",
                        "minimum_risk": 2,
                        "rule_key": "no-consequential-self-approval",
                    }
                ],
            },
            *[
                {
                    "decision_type": key,
                    "actions": actions,
                    "accountable_roles": accountable,
                    "veto_roles": vetoes,
                    "environments": ["*"],
                    "maximum_risk": risk,
                    "delegable": delegable,
                    "constitutional": constitutional,
                    "separation": separation,
                }
                for key, actions, accountable, vetoes, risk, delegable, constitutional, separation in [
                    ("research-program-charter", ["approve", "reject"], ["research"], ["governance"], 2, True, False, []),
                    ("trial-access", ["grant", "deny", "revoke"], ["governance"], ["security"], 2, True, False, []),
                    ("experiment-execution", ["authorize", "halt"], ["engineering"], ["governance"], 2, True, False, []),
                    ("evidence-admissibility", ["admit", "reject", "quarantine"], ["governance"], ["research"], 2, False, False, [{"field": "originator", "minimum_risk": 1, "rule_key": "independent-evidence-review"}]),
                    ("candidate-maturity", ["promote", "demote", "retire"], ["governance"], ["risk", "security", "production"], 3, False, False, [{"field": "originator", "minimum_risk": 1, "rule_key": "no-self-promotion"}, {"field": "evaluator", "minimum_risk": 1, "rule_key": "independent-promotion-authorization"}]),
                    ("portfolio-admission", ["admit", "remove"], ["governance"], ["risk"], 3, False, False, [{"field": "originator", "minimum_risk": 0, "rule_key": "independent-portfolio-admission"}]),
                    ("production-eligibility", ["approve", "revoke"], ["production"], ["risk", "security", "engineering"], 3, False, False, [{"field": "originator", "minimum_risk": 0, "rule_key": "independent-production-authorization"}]),
                    ("capital-allocation", ["allocate", "reduce", "halt"], ["production"], ["risk"], 3, False, True, [{"field": "originator", "minimum_risk": 0, "rule_key": "human-capital-authority"}]),
                    ("emergency-containment", ["halt", "isolate", "revoke", "quarantine", "reduce"], ["production", "governance"], [], 3, True, True, []),
                    ("canonical-knowledge-status", ["accept", "supersede", "retract"], ["knowledge"], ["governance", "security"], 2, True, False, [{"field": "originator", "minimum_risk": 1, "rule_key": "independent-knowledge-adjudication"}]),
                    ("policy-exception", ["approve", "reject", "close"], ["governance"], ["security", "risk"], 3, False, True, [{"field": "requester", "minimum_risk": 0, "rule_key": "independent-exception-approval"}]),
                ]
            ],
        ],
        "constitutional_boundaries": [
            "human-capital-authority",
            "no-capital-from-research",
            "no-secret-disclosure",
            "no-evidence-fabrication",
            "emergency-risk-reduction-only",
        ],
    }


def main() -> int:
    manifest = build_manifest()
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    with httpx.Client(base_url=base, headers=headers, timeout=30) as client:
        created = client.post(
            "/v1/authority/policies",
            json={"manifest": manifest, "manifest_digest": digest(manifest), "created_by": "founder-operator"},
        )
        created.raise_for_status()
        policy = created.json()
        if policy["status"] == "active":
            print(json.dumps(policy, indent=2))
            return 0
        activated = client.post(
            f"/v1/authority/policies/{policy['id']}/activate",
            json={"actor": "founder-operator", "reason": "Activate the GOV-001 institutional authority baseline."},
        )
        activated.raise_for_status()
        print(json.dumps(activated.json(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
