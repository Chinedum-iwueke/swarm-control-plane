import json

import httpx
import pytest

from hermes_telegram_gateway.control_plane import FounderChannelClient


@pytest.mark.asyncio
async def test_channel_uses_scoped_bearer_and_redacts_it() -> None:
    token = "founder-channel-secret-that-is-long-enough"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {token}"
        return httpx.Response(500, json={"detail": token})

    client = FounderChannelClient(
        "http://control-plane.test",
        token,
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(RuntimeError) as raised:
            await client.proposals()
    finally:
        await client.close()
    assert token not in str(raised.value)


@pytest.mark.asyncio
async def test_proposal_decision_body_is_bounded() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"status": "materialized"})

    client = FounderChannelClient(
        "http://control-plane.test",
        "founder-channel-secret-that-is-long-enough",
        transport=httpx.MockTransport(handler),
    )
    try:
        await client.decide_proposal(
            "proposal-id", "materialize", "Founder reviewed exact digest."
        )
    finally:
        await client.close()
    assert captured == {
        "reason": "Founder reviewed exact digest.",
        "expires_in_seconds": 900,
    }
