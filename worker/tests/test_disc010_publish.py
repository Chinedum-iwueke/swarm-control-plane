from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import httpx

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/disc010_publish.py"
SPEC = importlib.util.spec_from_file_location("disc010_publish", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
publish = MODULE.publish


def receipt(digest: str) -> dict:
    return {
        "schema_version": "bulletproof-producer-receipt-v1.0.0",
        "milestone": "DISC-010",
        "producer": (
            "bt.institutional.ohlcv_surveillance."
            "ohlcv_signal_surveillance_receipt"
        ),
        "receipt_digest": digest,
    }


def test_publisher_registers_once_and_recovers_remote_state(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    first = root / "family-a"
    second = root / "family-b"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "receipt.json").write_text(json.dumps(receipt("a" * 64)))
    (second / "receipt.json").write_text(json.dumps(receipt("b" * 64)))
    posted = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "remote-b",
                        "milestone": "DISC-010",
                        "receipt_digest": "b" * 64,
                    }
                ],
            )
        posted.append(json.loads(request.content))
        return httpx.Response(201, json={"id": "new-a"})

    state = tmp_path / "publisher-state.json"
    with httpx.Client(
        base_url="http://control-plane",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = publish(client=client, output_root=root, state_path=state)
        replay = publish(client=client, output_root=root, state_path=state)

    assert result == {
        "event": "disc010_publication_complete",
        "published": 1,
        "recovered": 1,
        "already_registered": 0,
        "registered_total": 2,
        "authority": "research_only",
    }
    assert replay["already_registered"] == 2
    assert len(posted) == 1
    assert posted[0]["registered_by"] == "disc010-vm1-publisher"
    assert state.stat().st_mode & 0o777 == 0o600


def test_publisher_rejects_noncanonical_receipt(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    family = root / "family-a"
    family.mkdir(parents=True)
    (family / "receipt.json").write_text(
        json.dumps(receipt("a" * 64) | {"milestone": "ML-002"})
    )

    with httpx.Client(
        base_url="http://control-plane",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[])),
    ) as client:
        try:
            publish(client=client, output_root=root, state_path=tmp_path / "state.json")
        except ValueError as exc:
            assert "noncanonical" in str(exc)
        else:
            raise AssertionError("noncanonical receipt was published")
