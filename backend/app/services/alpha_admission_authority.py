"""Resolve admission authority without expanding a mandate's approved dataset scope."""
from uuid import UUID

from fastapi import HTTPException

from app.models.quantitative_receipt import QuantitativeProducerReceipt


def admission_authority(db, specification, data):
    catalog = specification.get("discovery_catalog")
    if catalog is not None:
        return {**catalog, "basis": "discovery_catalog"}
    selected = []
    for instrument in data["instruments"]:
        matches = []
        for binding in specification.get("dataset_bindings", []):
            record = db.get(QuantitativeProducerReceipt, UUID(str(binding["producer_receipt_id"])))
            if record is None:
                continue
            result = record.receipt.get("result", {})
            if (result.get("venue"), result.get("instrument"), result.get("timeframe")) != (
                data["venue"], instrument, data["timeframe"]
            ):
                continue
            if (
                record.source_commit != specification["bulletproof_source_commit"]
                or record.receipt_digest != binding.get("producer_receipt_digest")
                or record.dataset_digest not in binding["partition_digests"]
                or result.get("panel_sha256") != record.dataset_digest
                or result.get("admitted") is not True
                or any(record.receipt.get("authority", {}).values())
            ):
                raise HTTPException(409, "Approved admission receipt no longer matches its source and bytes.")
            matches.append({"venue": data["venue"], "instrument": instrument,
                            "timeframe": data["timeframe"],
                            "panel_digest": record.dataset_digest,
                            "producer_receipt_id": str(record.id),
                            "receipt_digest": record.receipt_digest})
        unique = {(m["producer_receipt_id"], m["panel_digest"]): m for m in matches}
        if len(unique) != 1:
            raise HTTPException(409, "Candidate requires exactly one approved dataset binding per selected panel.")
        selected.append(next(iter(unique.values())))
    if not selected:
        raise HTTPException(409, "Candidate has no approved selected panels.")
    # Legacy transport names carry an anchor receipt, not a fabricated manifest.
    # The complete exact-byte scope is frozen separately in task approval_policy.
    return {"basis": "approved_dataset_bindings", "panels": selected,
            "producer_receipt_id": selected[0]["producer_receipt_id"],
            "receipt_digest": selected[0]["receipt_digest"]}


def require_approved_panel_bytes(authority, receipts):
    if authority["basis"] != "approved_dataset_bindings":
        return
    expected = {(p["venue"], p["instrument"], p["timeframe"]): p["panel_digest"]
                for p in authority["panels"]}
    observed = {}
    for receipt in receipts:
        result = receipt.get("result", {})
        key = (result.get("venue"), result.get("instrument"), result.get("timeframe"))
        if key in observed or receipt.get("dataset_digest") != result.get("panel_sha256"):
            raise HTTPException(409, "Admission result duplicates a panel or changes its byte identity.")
        observed[key] = result.get("panel_sha256")
    if observed != expected:
        raise HTTPException(409, "Admission result changes founder-approved panel bytes.")
