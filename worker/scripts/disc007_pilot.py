#!/usr/bin/env python3
"""Run a bounded no-capital DISC-007 selection-bias audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

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
        default=Path("/var/lib/invariance-swarm/disc007/report.json"),
    )
    args = parser.parse_args()
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=90,
    ) as client:
        existing = next(
            (
                item
                for item in call(client, "GET", "/v1/research/selection-audits")
                if item["audit_key"] == "DISC007-LIVE-AUDIT-R1"
            ),
            None,
        )
        if existing is None:
            mechanism = call(client, "GET", "/v1/research/falsification/evaluations")[0]
            ledger = family_ledger()
            existing = call(
                client,
                "POST",
                "/v1/research/selection-audits",
                json={
                    "audit_key": "DISC007-LIVE-AUDIT-R1",
                    "mechanism_evaluation_id": mechanism["id"],
                    "ledger": ledger,
                    "ledger_digest": digest(ledger),
                    "correction_policy": {
                        "alpha": 0.05,
                        "effective_trial_count": 4,
                        "maximum_pbo": 0.5,
                    },
                    "audited_by": "independent-statistical-reviewer",
                },
            )
    report = {
        "schema_version": "disc007-pilot-report-v1.0.0",
        "success": existing["conclusion"] == "selection_risk_detected",
        "audit_id": existing["id"],
        "audit_digest": existing["audit_digest"],
        "ledger_digest": existing["ledger_digest"],
        "conclusion": existing["conclusion"],
        "family_wise_p": existing["audit"]["family_wise_p"],
        "nominal_winner_p": 0.02,
        "failed_and_cancelled_trials_retained": existing["audit"]["failed_trials"]
        + existing["audit"]["cancelled_trials"]
        == 2,
        "promotion_authority": existing["audit"]["promotion_authority"],
        "execution_order_or_capital_authority": False,
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


def family_ledger() -> dict:
    trials = []
    for number, p_value, sharpe in ((1, 0.02, 1.2), (2, 0.4, 0.1)):
        trials.append(
            {
                "trial_key": f"trial-{number}",
                "specification_digest": digest({"trial": number}),
                "status": "completed",
                "primary_metric": sharpe,
                "p_value": p_value,
                "sharpe": sharpe,
                "sharpe_standard_error": 0.1,
            }
        )
    trials.extend(
        [
            {
                "trial_key": "trial-3",
                "specification_digest": digest({"trial": 3}),
                "status": "failed",
            },
            {
                "trial_key": "trial-4",
                "specification_digest": digest({"trial": 4}),
                "status": "cancelled",
            },
        ]
    )
    return {
        "schema_version": 1,
        "search_plan_digest": digest({"search_plan": "DISC007-LIVE"}),
        "trial_family": "DISC007-LIVE-FAMILY",
        "planned_trial_count": 4,
        "trials": trials,
        "reported_winner_trial_key": "trial-1",
        "stopping": {
            "rule_digest": digest({"rule": "fixed-family", "count": 4}),
            "rule_kind": "fixed_family",
            "stopped_after_trial": 4,
            "stop_reason": "family_complete",
            "outcome_access_before_stop": False,
        },
        "declared_researcher_degrees": ["parameter-grid", "seed-set"],
        "observed_research_operations": ["parameter-grid", "seed-set"],
        "validation_splits": [
            {"split_key": "split-1", "winner_rank": 1, "candidate_count": 4},
            {"split_key": "split-2", "winner_rank": 2, "candidate_count": 4},
            {"split_key": "split-3", "winner_rank": 3, "candidate_count": 4},
            {"split_key": "split-4", "winner_rank": 2, "candidate_count": 4},
        ],
        "finalized_at": datetime(2026, 8, 27, 18, tzinfo=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
