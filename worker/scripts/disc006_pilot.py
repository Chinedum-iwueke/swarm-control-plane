#!/usr/bin/env python3
"""Exercise preregistered mechanism falsification against live governed evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def call(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"{method} {path} returned HTTP {response.status_code}: {response.text}"
        ) from exc
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/var/lib/invariance-swarm/disc006/report.json"),
    )
    args = parser.parse_args()
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=90,
    ) as client:
        evaluations = call(client, "GET", "/v1/research/falsification/evaluations")
        existing = next(
            (
                item
                for item in evaluations
                if item["evaluation_key"] == "DISC006-LIVE-UNRESOLVED-R1"
            ),
            None,
        )
        if existing:
            falsified = next(
                item
                for item in evaluations
                if item["id"] == existing["supersedes_evaluation_id"]
            )
            report = make_report(falsified, existing)
        else:
            mapped = next(
                item
                for item in call(
                    client, "GET", "/v1/research/discovery-maps?status=active&limit=500"
                )
                if item["stage"] in {"mechanism", "opportunity"}
            )
            hypothesis = call(client, "GET", "/v1/research/hypotheses")[0]
            result = call(
                client,
                "GET",
                "/v1/research/evidence/objects?object_type=result&limit=1",
            )["items"][0]
            claims = call(
                client,
                "GET",
                f"/v1/research/evidence/objects?object_type=claim&project={result['project']}&limit=1",
            )["items"]
            claim = claims[0] if claims else register_claim(client, result)
            oppositions = call(client, "GET", "/v1/research/memory/oppositions")
            opposition = (
                oppositions[0]
                if oppositions
                else call(
                    client,
                    "POST",
                    "/v1/research/memory/oppositions",
                    json={
                        "project": result["project"],
                        "subject_claim_id": claim["object_id"],
                        "opposing_object_id": result["object_id"],
                        "opposition_type": "alternative_explanation",
                        "comparability": {
                            "population": "Existing governed Bulletproof research result",
                            "horizon": "Existing result horizon",
                            "method": "Provenance fixture for the DISC-006 governance replay",
                            "materially_comparable": False,
                            "unresolved_differences": [
                                "The replay proves governance behavior, not economic comparability."
                            ],
                        },
                        "rationale": "The retained negative result is an explicit rival to an unqualified positive mechanism claim.",
                        "recorded_by": "disc006-pilot",
                    },
                )
            )
            claim = call(
                client,
                "GET",
                f"/v1/research/evidence/objects/{opposition['subject_claim_id']}",
            )
            opposing = call(
                client,
                "GET",
                f"/v1/research/evidence/objects/{opposition['opposing_object_id']}",
            )
            dossiers = call(client, "GET", "/v1/research/memory/dossiers")
            dossier = (
                dossiers[0]
                if dossiers
                else call(
                    client,
                    "POST",
                    "/v1/research/memory/dossiers",
                    json={
                        "dossier_key": "DISC006-LIVE-PREREQUISITE",
                        "version": "1.0.0",
                        "project": opposition["project"],
                        "access_class": opposing["access_class"],
                        "question": mapped["document"]["question"],
                        "decision_context": "Freeze mechanism alternatives before decisive outcomes.",
                        "scope": mapped["document"]["baseline_definition"],
                        "evidence_cutoff": datetime.now().astimezone().isoformat(),
                        "claim_ids": [claim["object_id"]],
                        "supporting_evidence_ids": [],
                        "opposing_evidence_ids": [opposing["object_id"]],
                        "belief_ids": [],
                        "opposition_record_ids": [opposition["id"]],
                        "outcome_record_ids": [],
                        "episode_ids": [],
                        "retrieval_manifest": {
                            "mode": "exact-opposition-replay",
                            "object_ids": [claim["object_id"], opposing["object_id"]],
                        },
                        "doctrine_and_authority": [
                            "Research Bible falsification boundary"
                        ],
                        "unknowns": [
                            "Economic mechanism remains unresolved before testing."
                        ],
                        "risks": ["Confounding and post-hoc interpretation."],
                        "dissent": [opposition["rationale"]],
                        "synthesis": "The frozen record retains both the subject claim and its explicit opposition.",
                        "recommendation": "Preregister the decisive test before evaluating outcomes.",
                        "compiler_version": "disc006-pilot-v1.0.0",
                        "compiled_by": "disc006-pilot",
                    },
                )
            )
            evidence = opposing
            plan_document = {
                "schema_version": 1,
                "mechanism": "Reduced liquidity amplifies the price response to directional forced flow.",
                "scope": "The active DISC-002 BTC opportunity population and evidence cutoff.",
                "assumptions": [
                    "The declared liquidity proxy preserves ordinal depth information."
                ],
                "alternatives": [
                    {
                        "explanation_key": "volatility-confounding",
                        "claim": "The mapped effect is entirely explained by volatility and calendar clustering.",
                        "confounders": ["realized-volatility", "calendar-regime"],
                    }
                ],
                "decisive_tests": [
                    {
                        "test_key": "matched-regime-test",
                        "prediction": "The incremental effect remains positive after matching volatility and calendar regime.",
                        "null_expectation": "The incremental effect is indistinguishable from zero after matching regimes.",
                        "falsifies_when": "The matched result fails the preregistered positive incremental boundary.",
                        "target_alternatives": ["volatility-confounding"],
                        "analysis_digest": digest(
                            {"test": "matched-regime-test", "version": 1}
                        ),
                    }
                ],
                "dossier_ids": [dossier["id"]],
                "opposition_record_ids": [opposition["id"]],
                "evidence_cutoff": utc_text(datetime.now().astimezone()),
            }
            plans = call(client, "GET", "/v1/research/falsification/plans")
            plan = next(
                (item for item in plans if item["plan_key"] == "DISC006-LIVE-PLAN-R1"),
                None,
            )
            if plan is None:
                plan = call(
                    client,
                    "POST",
                    "/v1/research/falsification/plans",
                    json={
                        "plan_key": "DISC006-LIVE-PLAN-R1",
                        "discovery_map_id": mapped["id"],
                        "hypothesis_id": hypothesis["id"],
                        "plan": plan_document,
                        "plan_digest": digest(plan_document),
                        "registered_by": "disc006-pilot",
                    },
                )
            outcome_time = datetime.fromisoformat(
                plan["registered_at"].replace("Z", "+00:00")
            ) + timedelta(microseconds=1)
            outcome_time_text = utc_text(outcome_time)
            failed_document = evaluation(
                plan["plan_digest"], evidence, outcome_time_text, "failed", "ruled_out"
            )
            falsified = next(
                (
                    item
                    for item in evaluations
                    if item["evaluation_key"] == "DISC006-LIVE-FALSIFIED-R1"
                ),
                None,
            )
            if falsified is None:
                falsified = call(
                    client,
                    "POST",
                    "/v1/research/falsification/evaluations",
                    json={
                        "evaluation_key": "DISC006-LIVE-FALSIFIED-R1",
                        "plan_id": plan["id"],
                        "evaluation": failed_document,
                        "evaluation_digest": digest(failed_document),
                        "evaluated_by": "independent-reviewer",
                    },
                )
            unresolved_document = evaluation(
                plan["plan_digest"],
                evidence,
                outcome_time_text,
                "inconclusive",
                "inconclusive",
            )
            existing = call(
                client,
                "POST",
                "/v1/research/falsification/evaluations",
                json={
                    "evaluation_key": "DISC006-LIVE-UNRESOLVED-R1",
                    "plan_id": plan["id"],
                    "evaluation": unresolved_document,
                    "evaluation_digest": digest(unresolved_document),
                    "supersedes_evaluation_id": falsified["id"],
                    "evaluated_by": "independent-reviewer",
                },
            )
            report = make_report(falsified, existing)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def evaluation(
    plan_digest: str, evidence: dict, evaluated_at: str, outcome: str, rival: str
) -> dict:
    return {
        "schema_version": 1,
        "plan_digest": plan_digest,
        "outcomes": [
            {
                "test_key": "matched-regime-test",
                "outcome": outcome,
                "observed_result": "The retained decisive-test result was evaluated against the preregistered boundary.",
                "evidence_object_id": evidence["object_id"],
                "evidence_digest": evidence["content_digest"],
                "rival_outcomes": {"volatility-confounding": rival},
            }
        ],
        "evaluated_at": evaluated_at,
        "limitations": [
            "The pilot proves governance behavior, not the economic mechanism."
        ],
    }


def utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def register_claim(client: httpx.Client, result: dict) -> dict:
    native_id = "disc006-live-claim-r1"
    payload = {
        "kind": "claim",
        "proposition": "Reduced liquidity amplifies the price response to directional forced flow.",
        "evidence_object_ids": [result["object_id"]],
        "qualifiers": [
            "Governance fixture only; the referenced result does not establish the mechanism."
        ],
        "status": "disputed",
    }
    return call(
        client,
        "POST",
        "/v1/research/evidence/objects",
        json={
            "schema_version": "canonical-identity-v1.0.0",
            "object_schema_version": "canonical-evidence-v1.0.0",
            "object_id": str(uuid5(NAMESPACE_URL, native_id)),
            "object_type": "claim",
            "content_version": "1.0.0",
            "content_digest": digest(payload),
            "producer": {
                "system": "disc006-pilot",
                "native_type": "claim",
                "native_id": native_id,
                "schema_version": "disc006-pilot-v1.0.0",
            },
            "aliases": [
                {
                    "namespace": "disc006-pilot",
                    "object_type": "claim",
                    "value": native_id,
                }
            ],
            "project": result["project"],
            "access_class": result["access_class"],
            "authority_class": "derived",
            "payload": payload,
            "created_by": "disc006-pilot",
        },
    )


def make_report(falsified: dict, unresolved: dict) -> dict:
    report = {
        "schema_version": "disc006-pilot-report-v1.0.0",
        "success": falsified["conclusion"] == "falsified"
        and unresolved["conclusion"] == "unresolved"
        and unresolved["supersedes_evaluation_id"] == falsified["id"],
        "falsified_evaluation_id": falsified["id"],
        "falsified_evaluation_digest": falsified["evaluation_digest"],
        "superseding_unresolved_evaluation_id": unresolved["id"],
        "failed_decisive_test_visible": True,
        "source_write_authority": False,
        "execution_order_or_capital_authority": False,
    }
    report["report_digest"] = digest(report)
    return report


if __name__ == "__main__":
    raise SystemExit(main())
