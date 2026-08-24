import json

import httpx
import pytest

from hermes_telegram_gateway.control_plane import FounderChannelClient
from hermes_telegram_gateway.telegram import TelegramClient, split_message


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


def test_long_messages_are_split_without_losing_content() -> None:
    text = "A" * 3990 + "\n" + "B" * 3990 + "\n" + "C" * 500
    chunks = split_message(text)

    assert all(0 < len(chunk) <= 4000 for chunk in chunks)
    assert "".join(chunks) == text


@pytest.mark.asyncio
async def test_telegram_client_requests_edits_and_places_button_on_last_chunk() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append({"path": request.url.path, "body": body})
        if request.url.path.endswith("getUpdates"):
            return httpx.Response(200, json={"ok": True, "result": []})
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": len(requests)}},
        )

    client = TelegramClient(
        "telegram-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        await client.updates(17, 25)
        sent = await client.send(
            456,
            "A" * 4500,
            button_text="Review",
            button_url="https://t.me/example",
        )
    finally:
        await client.close()

    assert requests[0]["body"]["offset"] == 17
    assert requests[0]["body"]["allowed_updates"] == [
        "message",
        "edited_message",
    ]
    sends = requests[1:]
    assert len(sends) == 2
    assert "reply_markup" not in sends[0]["body"]
    assert sends[1]["body"]["reply_markup"]["inline_keyboard"][0][0]["text"] == "Review"
    assert len(sent) == 2
