from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.alpha_admission_authority import admission_authority, require_approved_panel_bytes


def fixture():
    rid = uuid4()
    result = dict(venue="bybit", instrument="BTCUSDT", timeframe="1m",
                  panel_sha256="a" * 64, admitted=True)
    record = SimpleNamespace(id=rid, source_commit="b" * 40, dataset_digest="a" * 64,
                             receipt_digest="c" * 64,
                             receipt={"result": result, "authority": {"orders": False}})
    binding = dict(producer_receipt_id=str(rid), producer_receipt_digest="c" * 64,
                   partition_digests=["a" * 64])
    spec = dict(discovery_catalog=None, dataset_bindings=[binding], bulletproof_source_commit="b" * 40)
    data = dict(venue="bybit", instruments=["BTCUSDT"], timeframe="1m", required_fields=["close"])
    return Mock(get=Mock(return_value=record)), spec, data, record


def test_exact_approved_bindings_are_not_promoted_to_discovery_catalogs():
    db, spec, data, _ = fixture()
    before = deepcopy(spec)
    result = admission_authority(db, spec, data)
    assert result["basis"] == "approved_dataset_bindings"
    assert result["panels"][0]["panel_digest"] == "a" * 64
    assert spec == before
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("change", ["source", "bytes", "digest", "authority", "unadmitted", "asset", "missing", "ambiguous"])
def test_fallback_does_not_expand_or_repair_approved_scope(change):
    db, spec, data, record = fixture()
    if change == "source": record.source_commit = "d" * 40
    if change == "bytes": record.dataset_digest = "d" * 64
    if change == "digest": record.receipt_digest = "d" * 64
    if change == "authority": record.receipt["authority"]["orders"] = True
    if change == "unadmitted": record.receipt["result"]["admitted"] = False
    if change == "asset": data["instruments"] = ["ETHUSDT"]
    if change == "missing": db.get.return_value = None
    if change == "ambiguous":
        other = deepcopy(record)
        other.id = uuid4()
        spec["dataset_bindings"].append({**spec["dataset_bindings"][0], "producer_receipt_id": str(other.id)})
        db.get.side_effect = [record, other]
    with pytest.raises(HTTPException) as caught:
        admission_authority(db, spec, data)
    assert caught.value.status_code == 409


def test_rechecked_bytes_must_match_all_approved_panels_exactly():
    db, spec, data, record = fixture()
    authority = admission_authority(db, spec, data)
    receipt = {"result": record.receipt["result"], "dataset_digest": record.dataset_digest}
    require_approved_panel_bytes(authority, [receipt])
    for receipts in [[], [receipt, receipt], [{**receipt, "dataset_digest": "d" * 64}],
                     [{"dataset_digest": "d" * 64, "result": {**receipt["result"], "panel_sha256": "d" * 64}}]]:
        with pytest.raises(HTTPException):
            require_approved_panel_bytes(authority, receipts)


def test_existing_discovery_catalog_does_not_use_binding_fallback():
    db, spec, data, _ = fixture()
    spec["discovery_catalog"] = {"producer_receipt_id": str(uuid4()), "receipt_digest": "d" * 64}
    result = admission_authority(db, spec, data)
    assert result["basis"] == "discovery_catalog"
    db.get.assert_not_called()


def test_admission_task_freezes_explicit_basis_without_worker_schema_change(monkeypatch):
    from app.services import alpha_discovery as service

    db, spec, data, _ = fixture()
    db.scalar.return_value = None
    mandate = SimpleNamespace(specification=spec, mandate_digest="e" * 64)
    candidate = SimpleNamespace(id=uuid4(), candidate_digest="f" * 64, document={"data": data})
    task = SimpleNamespace(id=uuid4())
    build = Mock(return_value=task)
    monkeypatch.setattr(service, "build_task", build)
    monkeypatch.setattr(service, "persist_new_task", Mock())
    service._ensure_data_admission_task(db, mandate, candidate)
    payload = build.call_args.args[0]
    assert payload.approval_policy["admission_basis"] == "approved_dataset_bindings"
    assert payload.approval_policy["approved_panels"][0]["panel_digest"] == "a" * 64
    assert payload.input_contract["assets"][0]["instrument"] == "BTCUSDT"
    assert payload.input_contract["catalog_receipt_digest"] == "c" * 64
