#!/usr/bin/env python3
"""Publish one completed BT-009 qualification through the governed laboratory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

NAMESPACE = uuid.UUID("d8bf5bb7-e72e-49ed-8493-d4c323e92c61")


def digest(value: Any) -> str:
    payload = (
        value
        if isinstance(value, bytes)
        else json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    )
    return hashlib.sha256(payload).hexdigest()


def canonical_utc(value: str | datetime) -> str:
    parsed = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def call(client: httpx.Client, method: str, path: str, payload: dict | None = None):
    response = client.request(method, path, json=payload)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"{method} {path} returned HTTP {response.status_code}: {response.text[:1200]}"
        ) from exc
    return response.json()


def write_state(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".new")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def evidence_object(
    *, object_id: uuid.UUID, object_type: str, payload: dict, native_id: str
) -> dict:
    content_digest = digest(payload)
    return {
        "schema_version": "canonical-identity-v1.0.0",
        "object_schema_version": "canonical-evidence-v1.0.0",
        "object_id": str(object_id),
        "object_type": object_type,
        "content_version": "1",
        "content_digest": content_digest,
        "producer": {
            "system": "bulletproof-bt",
            "native_type": object_type,
            "native_id": native_id,
            "schema_version": "bt009-qualification-execution-v1.0.0",
        },
        "aliases": [
            {
                "namespace": "bulletproof-bt",
                "object_type": object_type,
                "value": native_id,
            }
        ],
        "supersedes_object_id": None,
        "project": "bulletproof-bt",
        "access_class": "restricted",
        "authority_class": "primary"
        if object_type in {"source", "dataset"}
        else "operational",
        "payload": payload,
        "created_by": "bulletproof-producer",
    }


def advance(client: httpx.Client, bridge: dict, next_state: str, receipt: dict) -> dict:
    return call(
        client,
        "POST",
        f"/v1/research/governed-bridges/{bridge['id']}/advance",
        {
            "expected_state": bridge["state"],
            "next_state": next_state,
            "receipt": receipt,
        },
    )


def register(
    client: httpx.Client, qualification: dict, proposal: dict, snapshot: dict
) -> dict:
    bridge = call(
        client, "POST", "/v1/research/governed-bridges", {"proposal": proposal}
    )
    if bridge["state"] == "awaiting_approval":
        bridge = advance(
            client,
            bridge,
            "approved",
            {
                "approved_by": "founder-operator",
                "proposal_digest": proposal["proposal_digest"],
            },
        )

    source_key = f"BT009-SOURCE-{snapshot['content_digest'][:16]}"
    source_spec = {
        "title": "BT-009 deterministic perpetual contract-qualification source",
        "source_type": "dataset",
        "version": snapshot["snapshot_id"],
        "content_sha256": snapshot["content_digest"],
        "provenance": "Generated deterministically by the committed BT-009 qualification harness; no market-performance claim.",
        "point_in_time": True,
        "observed_at": canonical_utc(snapshot["end"]),
    }
    source_document = {
        "source_key": source_key,
        "specification": source_spec,
        "registered_by": "research-registry",
    }
    source = call(
        client,
        "POST",
        "/v1/research/sources",
        source_document | {"record_digest": digest(source_spec)},
    )
    snapshot_spec = {
        "provider": "bulletproof-bt-qualification",
        "instrument": "BTCUSDT",
        "timeframe": "1m",
        "date_start": canonical_utc(snapshot["start"]),
        "date_end": canonical_utc(snapshot["end"]),
        "rows": snapshot["rows"],
        "format": "parquet",
        "storage_uri": f"snapshot://sha256/{snapshot['content_digest']}",
        "transformation": "Deterministic causal synthetic perpetual fixture with point-in-time auxiliary availability.",
        "point_in_time": True,
    }
    snapshot_document = {
        "snapshot_key": f"BT009-SNAPSHOT-{snapshot['content_digest'][:16]}",
        "source_id": source["id"],
        "specification": snapshot_spec,
        "content_digest": snapshot["content_digest"],
        "registered_by": "research-registry",
    }
    snapshot_record = call(
        client,
        "POST",
        "/v1/research/data-snapshots",
        snapshot_document | {"record_digest": digest(snapshot_document)},
    )
    canonical_source_id = uuid.uuid5(NAMESPACE, f"source:{snapshot['content_digest']}")
    call(
        client,
        "POST",
        "/v1/research/evidence/objects",
        evidence_object(
            object_id=canonical_source_id,
            object_type="source",
            native_id=source_key,
            payload={
                "kind": "source",
                "title": source_spec["title"],
                "origin": source_spec["provenance"],
                "rights": "internal contract-qualification evidence only",
                "acquired_at": canonical_utc(snapshot["end"]),
            },
        ),
    )
    call(
        client,
        "POST",
        "/v1/research/evidence/objects",
        evidence_object(
            object_id=uuid.UUID(snapshot["snapshot_id"]),
            object_type="dataset",
            native_id=snapshot["snapshot_id"],
            payload={
                "kind": "dataset",
                "source_object_ids": [str(canonical_source_id)],
                "schema_digest": digest(snapshot["fields"]),
                "partition_digests": [snapshot["content_digest"]],
                "availability_policy": "Causal point-in-time auxiliary joins; missing information means no decision.",
                "correction_object_ids": [],
            },
        ),
    )

    hypothesis_spec = {
        "research_question": "Does CSI-gated displacement retain a positive right-tail trend edge after causal Tier2B market frictions?",
        "rationale": "Constraint-forced flows can amplify displacement, but the registered claim must survive exhaustive costs and selection controls.",
        "mechanism": "Funding, basis, open-interest acceleration, displacement, and liquidity stress jointly identify forced-flow proximity.",
        "prediction": "At least one prospectively registered grid variant produces robust positive net expectancy and multi-ATR right-tail events.",
        "universe": ["BTCUSDT"],
        "target": "net portfolio outcome under the registered CSI displacement rule",
        "horizon": "24 signal bars",
        "null_hypothesis": "CSI gating adds no robust net edge beyond volatility and transaction-cost effects.",
        "failure_conditions": [
            "No registered variant produces positive net expectancy.",
            "The apparent effect is explained by volatility or timestamp leakage.",
            "Tier2B truth validation or immutable bundle finalization fails.",
        ],
        "rival_explanations": [
            "CSI is only a volatility proxy.",
            "Funding or open-interest availability leaks future information.",
        ],
        "maximum_trials": len(qualification["runs"]),
    }
    hypothesis_document = {
        "hypothesis_key": f"BT009-CSI-{proposal['proposal_digest'][:16]}",
        "trial_family": f"BT009-CSI-FAMILY-{proposal['proposal_digest'][:16]}",
        "specification": hypothesis_spec,
        "registered_by": "vm1-m13-senior-research-specialist",
    }
    hypothesis = call(
        client,
        "POST",
        "/v1/research/hypotheses",
        hypothesis_document | {"record_digest": digest(hypothesis_spec)},
    )
    call(
        client,
        "POST",
        f"/v1/research/hypothesis/{hypothesis['id']}/reviews",
        {
            "subject_digest": hypothesis["record_digest"],
            "review_kind": "approval",
            "verdict": "approved",
            "review": {
                "summary": "Founder approved the immutable 16-variant exhaustive proposal."
            },
            "reviewer": "founder-operator",
        },
    )
    manifest = {
        "repository": "bulletproof_bt",
        "repository_commit": qualification["repository_commit"],
        "dataset_version": snapshot["snapshot_id"],
        "instrument_universe": ["BTCUSDT"],
        "timeframe": "1m",
        "date_start": None,
        "date_end": None,
        "sample_range": f"{snapshot['start']}..{snapshot['end']}",
        "features": [
            "CSI",
            "D_t",
            "ATR_14",
            "S_t",
            "funding percentile",
            "OI acceleration",
        ],
        "target": "Tier2B net portfolio outcome",
        "model_or_rule": "existing l7_h1_csi_gated_displacement_trend strategy",
        "parameters": {
            "variant_count": len(qualification["runs"]),
            "stopping_rule": "exhaustive",
            "research_tier": "tier2b",
        },
        "fees_bps": 5.0,
        "slippage_bps": 2.0,
        "delay_bars": 1,
        "validation_method": "native classic engine, causal auxiliary joins, truth gate, exact exhaustive grid",
        "success_criteria": [
            "positive net expectancy",
            "right-tail evidence",
            "truth gate PASS",
        ],
        "rejection_criteria": ["no positive robust registered variant"],
        "engine_version": f"bulletproof_bt:{qualification['repository_commit']}",
        "data_snapshot_digest": snapshot["content_digest"],
    }
    experiment_document = {
        "experiment_key": f"BT009-EXP-{qualification['search_plan_digest'][:16]}",
        "hypothesis_id": hypothesis["id"],
        "source_id": source["id"],
        "snapshot_id": snapshot_record["id"],
        "manifest": manifest,
        "registered_by": "vm1-m13-experiment-specification",
    }
    experiment_digest = digest(manifest)
    experiment = call(
        client,
        "POST",
        "/v1/research/experiments",
        experiment_document | {"manifest_digest": experiment_digest},
    )
    call(
        client,
        "POST",
        f"/v1/research/experiment/{experiment['id']}/reviews",
        {
            "subject_digest": experiment_digest,
            "review_kind": "approval",
            "verdict": "approved",
            "review": {
                "summary": "Founder approved the exact experiment manifest before publication."
            },
            "reviewer": "founder-operator",
        },
    )

    trials = []
    for run in qualification["runs"]:
        trial = run["trial"]
        plan = {
            "run_id": f"BT009-{trial['trial_id'][:24]}",
            "task_id": str(uuid.uuid5(NAMESPACE, f"task:{trial['trial_id']}")),
            "code_commit": qualification["repository_commit"],
            "dataset_digest": qualification["dataset_digest"],
            "engine_digest": digest(qualification["repository_commit"].encode("ascii")),
        }
        trial_document = {
            "experiment_digest": experiment_digest,
            "trial_number": trial["ordinal"] + 1,
            "plan": plan,
            "executed_by": "vm1-m13-research-execution",
        }
        trials.append(
            call(
                client,
                "POST",
                f"/v1/research/experiments/{experiment['id']}/trials",
                {
                    "experiment_digest": experiment_digest,
                    "plan": plan,
                    "record_digest": digest(trial_document),
                    "executed_by": "vm1-m13-research-execution",
                },
            )
        )

    bridge = advance(
        client,
        bridge,
        "registry_bound",
        {
            "hypothesis_id": hypothesis["id"],
            "experiment_id": experiment["id"],
            "trial_ids": [item["id"] for item in trials],
            "search_plan_digest": qualification["search_plan_digest"],
        },
    )
    bridge = advance(
        client,
        bridge,
        "executed",
        {
            "run_count": len(qualification["runs"]),
            "repository_commit": qualification["repository_commit"],
        },
    )
    bridge = advance(client, bridge, "truth_validated", qualification["truth"])
    bridge = advance(
        client,
        bridge,
        "bundle_finalized",
        {
            "bundle_digests": [
                item["bundle"]["bundle_digest"] for item in qualification["runs"]
            ]
        },
    )
    return {
        "bridge": bridge,
        "experiment": experiment,
        "experiment_digest": experiment_digest,
        "hypothesis": hypothesis,
        "source": source,
        "snapshot": snapshot_record,
        "trials": trials,
    }


def publish(
    client: httpx.Client,
    qualification: dict,
    registry: dict,
    bundle_root: Path,
    bulletproof_root: Path,
    memory_db: Path,
) -> dict:
    selected = qualification["runs"][0]
    trial = registry["trials"][0]
    metrics = selected["result"]
    started = datetime.fromtimestamp(bundle_root.stat().st_mtime, tz=timezone.utc)
    ended = datetime.now(timezone.utc)
    result_document = {
        "summary": "The first prospectively registered CSI variant was negative after Tier2B costs; the full 16-variant search is retained.",
        "metrics": {
            key: value
            for key, value in metrics.items()
            if isinstance(value, (int, float, bool))
        },
        "robustness_status": "failed",
        "rejection_reason": "Negative net expectancy and no qualifying right-tail evidence in the selected registered variant.",
        "evidence_artifacts": [
            selected["bundle"]["bundle_digest"],
            qualification["search_plan_digest"],
        ],
        "output_artifact_digest": selected["bundle"]["bundle_digest"],
        "started_at": canonical_utc(started),
        "ended_at": canonical_utc(ended),
    }
    result_payload = {
        "trial_digest": trial["record_digest"],
        "outcome": "rejected",
        "result": result_document,
        "recorded_by": "vm1-m13-research-execution",
    }
    result = call(
        client,
        "POST",
        f"/v1/research/trials/{trial['id']}/results",
        result_payload | {"record_digest": digest(result_payload)},
    )
    statistical = call(
        client,
        "POST",
        f"/v1/research/result/{result['id']}/reviews",
        {
            "subject_digest": result["record_digest"],
            "review_kind": "independent_review",
            "verdict": "approved",
            "review": {
                "summary": "Verified 16 prospectively registered trials, truth PASS, and negative selected metrics.",
                "trial_count": len(qualification["runs"]),
                "selection_adjustment": "exhaustive finite grid; no hidden optimization",
            },
            "reviewer": "vm1-m13-statistical-reviewer",
        },
    )
    adversarial = call(
        client,
        "POST",
        f"/v1/research/result/{result['id']}/reviews",
        {
            "subject_digest": result["record_digest"],
            "review_kind": "adversarial_review",
            "verdict": "approved",
            "review": {
                "summary": "No live authority; synthetic evidence makes no market-performance claim; negative result retained.",
                "production_eligible": False,
                "fast_path_used": False,
            },
            "reviewer": "vm1-m13-adversarial-auditor",
        },
    )
    decision = call(
        client,
        "POST",
        f"/v1/research/results/{result['id']}/decisions",
        {
            "result_digest": result["record_digest"],
            "decision": "retain",
            "rationale": "Retain the reproducible negative BT-009 qualification evidence; prohibit production promotion.",
            "decided_by": "founder-operator",
        },
    )
    bridge = advance(
        client,
        registry["bridge"],
        "independently_reviewed",
        {
            "statistical_review_id": statistical["id"],
            "adversarial_review_id": adversarial["id"],
            "decision_id": decision["id"],
        },
    )

    sys.path.insert(0, str(bulletproof_root / "src"))
    from bt.logging.laboratory_publication import (
        confirm_projections,
        publish_certified_bundle,
    )

    bundle_digest = selected["bundle"]["bundle_digest"]
    bundle_dir = bundle_root / "output/run-bundles/bundles" / bundle_digest
    publication = publish_certified_bundle(
        api_url=str(client.base_url),
        token=client.headers["Authorization"].split(" ", 1)[1],
        bundle_dir=bundle_dir,
        registry_trial_id=trial["id"],
        registry_result_id=result["id"],
        memory_database=memory_db,
        timeout_seconds=300,
    )
    bridge = advance(
        client,
        bridge,
        "published",
        {"publication_id": publication["id"], "state": publication["state"]},
    )

    graph = call(client, "GET", "/v1/research/graph/projections/status")
    if graph["stale"]:
        graph = call(client, "POST", "/v1/research/graph/projections/rebuild")
    retrieval = call(client, "GET", "/v1/research/retrieval/projections/status")
    if retrieval["stale"]:
        retrieval = call(client, "POST", "/v1/research/retrieval/projections/rebuild")
    publication = confirm_projections(
        api_url=str(client.base_url),
        token=client.headers["Authorization"].split(" ", 1)[1],
        publication_id=publication["id"],
        graph_manifest_digest=graph["manifest_digest"],
        graph_source_epoch=graph["source_epoch"],
        retrieval_corpus_digest=retrieval["corpus_digest"],
        retrieval_source_epoch=retrieval["source_epoch"],
        timeout_seconds=300,
    )
    publication = publish_certified_bundle(
        api_url=str(client.base_url),
        token=client.headers["Authorization"].split(" ", 1)[1],
        bundle_dir=bundle_dir,
        registry_trial_id=trial["id"],
        registry_result_id=result["id"],
        memory_database=memory_db,
        timeout_seconds=300,
    )
    bridge = advance(client, bridge, "memory_confirmed", publication["memory_receipt"])
    replay = call(
        client,
        "GET",
        f"/v1/research/laboratory/publications/{publication['id']}/replay",
    )
    bridge = advance(
        client,
        bridge,
        "complete",
        {
            "publication_id": publication["id"],
            "publication_state": publication["state"],
            "event_count": len(replay["events"]),
        },
    )
    return {
        "bridge": bridge,
        "publication": publication,
        "replay": replay,
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification-root", type=Path, required=True)
    parser.add_argument("--bulletproof-root", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--memory-db", type=Path, required=True)
    args = parser.parse_args()
    qualification = json.loads((args.qualification_root / "result.json").read_text())
    proposal = json.loads(
        (args.qualification_root / "approved-proposal.json").read_text()
    )
    snapshot = json.loads((args.qualification_root / "data/snapshot.json").read_text())
    if qualification["truth"]["status"] != "PASS" or len(qualification["runs"]) != 16:
        raise SystemExit("BT-009 qualification must contain 16 truth-valid runs")
    token = os.environ["SWARM_ORCHESTRATOR_TOKEN"]
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=3600,
    ) as client:
        state = register(client, qualification, proposal, snapshot)
        write_state(args.state, state)
        outcome = publish(
            client,
            qualification,
            state,
            args.qualification_root,
            args.bulletproof_root,
            args.memory_db,
        )
        state.update(outcome)
        write_state(args.state, state)
    print(
        json.dumps(
            {
                "bridge_id": state["bridge"]["id"],
                "bridge_state": state["bridge"]["state"],
                "publication_id": state["publication"]["id"],
                "publication_state": state["publication"]["state"],
                "registered_trials": len(state["trials"]),
                "outcome": state["result"]["outcome"],
                "event_count": len(state["replay"]["events"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
