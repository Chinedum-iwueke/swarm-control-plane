from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.quantitative_receipt import QuantitativeReceiptConflict, _digest, _validate_inventory_root


def root_and_shards():
    shards, descriptors = [], []
    for index, paths in enumerate((["canonical/a", "canonical/b"], ["raw/a", "raw/b"])):
        result = {"run_id": "run-one", "shard_index": index, "object_count": 2,
                  "objects": [{"partition_id": path} for path in paths],
                  "dispositions": {"cataloged_pending_quality": 2},
                  "assets": [["perp", "bybit", "ETHUSDT"]]}
        shard = SimpleNamespace(receipt={"result": result}, dataset_digest=str(index) * 64)
        shards.append(shard)
        descriptors.append({"shard_index": index, "object_count": 2,
                            "receipt_digest": str(index + 2) * 64,
                            "dataset_digest": shard.dataset_digest})
    receipt = {"source_commit": "a" * 40, "input_digest": _digest(descriptors),
               "dataset_digest": _digest([item["dataset_digest"] for item in descriptors]),
               "result": {"run_id": "run-one", "shards": descriptors, "shard_count": 2,
                          "object_count": 4, "dispositions": {"cataloged_pending_quality": 4},
                          "assets": [["perp", "bybit", "ETHUSDT"]],
                          "claim_boundary": "Content accounting only; not admission",
                          "group_labels_are_optional_metadata": True}}
    return receipt, shards


def test_complete_root_requires_all_registered_shards():
    receipt, shards = root_and_shards()
    db = MagicMock()
    db.scalar.side_effect = shards
    _validate_inventory_root(db, receipt)
    assert db.scalar.call_count == 2
    db.scalar.side_effect = [shards[0], None]
    with pytest.raises(QuantitativeReceiptConflict, match="not registered"):
        _validate_inventory_root(db, receipt)


@pytest.mark.parametrize("change", ["run", "count", "digest", "overlap", "summary", "assets"])
def test_root_rejects_conflicting_custody_and_fabricated_summaries(change):
    receipt, shards = root_and_shards()
    receipt = deepcopy(receipt)
    if change == "run":
        shards[1].receipt["result"]["run_id"] = "different-run"
    elif change == "count":
        shards[1].receipt["result"]["object_count"] = 3
    elif change == "digest":
        shards[1].dataset_digest = "f" * 64
    elif change == "overlap":
        shards[1].receipt["result"]["objects"][0]["partition_id"] = "canonical/a"
    elif change == "summary":
        receipt["result"]["dispositions"] = {"quarantined": 4}
    else:
        receipt["result"]["assets"] = [["perp", "bybit", "BTCUSDT"]]
    db = MagicMock()
    db.scalar.side_effect = shards
    with pytest.raises(QuantitativeReceiptConflict):
        _validate_inventory_root(db, receipt)
