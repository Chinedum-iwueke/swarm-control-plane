from __future__ import annotations

import pytest

from hermes_mission_control.overview_events import (
    OverviewEventBroker,
    SubscriberLimitExceeded,
)


def snapshot(*, active: int = 1, freshness: str = "current") -> dict:
    return {
        "provenance": {
            "generated_at": "2026-10-21T00:00:00+00:00",
            "freshness": freshness,
        },
        "operation_summary": {"active_total": active},
        "approval_center": {"counts": {"actionable": 2}},
    }


@pytest.mark.asyncio
async def test_replays_missed_events_once_and_deduplicates_unchanged_snapshot():
    async def loader():
        return snapshot()

    broker = OverviewEventBroker(loader, replay_capacity=8)
    first = await broker.publish_snapshot(snapshot())
    assert first is not None
    assert await broker.publish_snapshot(snapshot()) is None
    second = await broker.publish_snapshot(snapshot(active=2))
    assert second is not None

    subscription = await broker.subscribe(str(first.event_id))
    assert [event.event_id for event in subscription.replay] == [second.event_id]
    assert subscription.replay[0].data["active_operations"] == 2
    await broker.unsubscribe(subscription)


@pytest.mark.asyncio
async def test_reports_expired_cursor_instead_of_partial_replay():
    async def loader():
        return snapshot()

    broker = OverviewEventBroker(loader, replay_capacity=2)
    await broker.publish_snapshot(snapshot(active=1))
    await broker.publish_snapshot(snapshot(active=2))
    await broker.publish_snapshot(snapshot(active=3))

    subscription = await broker.subscribe("0")
    assert subscription.cursor_state == "expired"
    assert subscription.replay == []
    await broker.unsubscribe(subscription)


@pytest.mark.asyncio
async def test_enforces_subscriber_budget_and_never_serializes_unknown_snapshot_fields():
    async def loader():
        return snapshot()

    broker = OverviewEventBroker(loader, max_subscribers=1, max_payload_bytes=512)
    event = await broker.publish_snapshot(
        {**snapshot(), "orchestrator_token": "never-browser"}
    )
    assert event is not None
    assert "orchestrator_token" not in event.data
    first = await broker.subscribe(None)
    with pytest.raises(SubscriberLimitExceeded):
        await broker.subscribe(None)
    await broker.unsubscribe(first)


@pytest.mark.asyncio
async def test_documented_subscriber_budget_fans_out_one_bounded_event():
    async def loader():
        return snapshot()

    broker = OverviewEventBroker(loader, max_subscribers=12, queue_capacity=16)
    subscribers = [await broker.subscribe(None) for _ in range(12)]
    with pytest.raises(SubscriberLimitExceeded):
        await broker.subscribe(None)

    published = await broker.publish_snapshot(snapshot(active=4))
    assert published is not None
    delivered = [subscriber.queue.get_nowait() for subscriber in subscribers]
    assert [event.event_id for event in delivered] == [published.event_id] * 12
    for subscriber in subscribers:
        await broker.unsubscribe(subscriber)
