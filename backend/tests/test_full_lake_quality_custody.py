from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.quantitative_receipt import QuantitativeReceiptConflict, _validate_full_lake_quality


def documents():
    source = {"partition_id": "canonical/perp/bybit/ETHUSDT/timeframe=1m/research_panel.parquet",
              "layer": "canonical", "dataset": "research_panel", "content_digest": "a" * 64,
              "market": "perp", "venue": "bybit", "instrument": "ETHUSDT", "timeframe": "1m",
              "disposition": "cataloged_pending_quality"}
    item = {key: value for key, value in source.items() if key not in ("layer", "dataset")}
    item.update(execution_eligible=False, panel_quality_passed=True,
                disposition="panel_quality_passed", checks={key: True for key in (
                    "nonempty_window", "complete_window_grid", "strict_timestamp_order",
                    "no_internal_gaps", "aligned_timestamps", "no_null_timestamps",
                    "required_fields_nonnull", "path_exchange_symbol_consistent", "valid_ohlcv")},
                reason_codes=[])
    inventory = SimpleNamespace(dataset_digest="b" * 64,
                                receipt={"result": {"object_count": 2, "objects": [source]}})
    receipt = {"dataset_digest": "b" * 64, "result": {
        "schema_version": "data003-full-lake-quality-v1.0.0", "objects": [item], "object_count": 1,
        "inventoried_object_count": 2, "unprocessed_dispositions": {"non_panel_adapter_required": 1},
        "dispositions": {"panel_quality_passed": 1},
        "inventory_receipt_digest": "c" * 64, "claim_boundary": "Base panel only, no admission"}}
    receipt["result"].update(window_start="2025-05-01T00:00:00+00:00", window_end="2026-05-01T00:00:00+00:00")
    return receipt, inventory


def test_quality_requires_registered_bound_inventory():
    receipt, inventory = documents()
    db = MagicMock()
    db.scalar.return_value = inventory
    _validate_full_lake_quality(db, receipt)
    db.scalar.return_value = None
    with pytest.raises(QuantitativeReceiptConflict, match="complete bound"):
        _validate_full_lake_quality(db, receipt)


@pytest.mark.parametrize("change", ["digest", "identity", "authority", "count", "check", "invented", "summary", "source_quarantined"])
def test_quality_cannot_invent_source_or_infer_execution(change):
    receipt, inventory = documents()
    receipt = deepcopy(receipt)
    if change == "digest":
        receipt["result"]["objects"][0]["content_digest"] = "e" * 64
    elif change == "identity":
        receipt["result"]["objects"][0]["instrument"] = "BTCUSDT"
    elif change == "authority":
        receipt["result"]["objects"][0]["execution_eligible"] = True
    elif change == "count":
        receipt["result"]["inventoried_object_count"] = 999
    elif change == "check":
        receipt["result"]["objects"][0]["checks"]["valid_ohlcv"] = False
    elif change == "invented":
        receipt["result"]["objects"][0]["checks"] = {"invented": True}
    elif change == "summary":
        receipt["result"]["dispositions"] = {"quarantined": 1}
    else:
        inventory.receipt["result"]["objects"][0]["disposition"] = "quarantined"
    db = MagicMock()
    db.scalar.return_value = inventory
    with pytest.raises(QuantitativeReceiptConflict):
        _validate_full_lake_quality(db, receipt)
