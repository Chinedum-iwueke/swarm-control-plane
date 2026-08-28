from pathlib import Path


def test_replay_success_is_bound_to_supplied_batch_size():
    source = (
        Path(__file__).parents[1] / "scripts" / "quantitative_receipt_replay.py"
    ).read_text(encoding="utf-8")
    assert 'if not receipts:' in source
    assert '"expected_receipts": len(receipts)' in source
    assert '"success": len(registered) == len(receipts)' in source
    assert "len(registered) == 15" not in source
