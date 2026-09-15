import os
from datetime import UTC, datetime, timedelta

import pytest
from app.models.alpha_discovery import AlphaDiscoveryEvent, AlphaResearchMandate
from app.services.alpha_discovery import _event
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_multiple_discovery_events_share_one_transaction_without_sequence_collision():
    url = os.environ.get("ALPHA_DISCOVERY_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set ALPHA_DISCOVERY_TEST_DATABASE_URL for isolated PostgreSQL replay."
        )
    assert url.startswith("postgresql+psycopg://")
    assert url.endswith("/hermes_discovery_test")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE alpha_discovery_cycles (id uuid PRIMARY KEY)"
            )
            AlphaResearchMandate.__table__.create(connection)
            AlphaDiscoveryEvent.__table__.create(connection)
        with Session(engine, autoflush=False) as db:
            moment = datetime.now(UTC)
            mandate = AlphaResearchMandate(
                mandate_key="transaction-replay",
                version="1.0.0",
                objective="Retain bounded test events.",
                specification={},
                budget={},
                mandate_digest="a" * 64,
                created_by="test",
                valid_from=moment,
                valid_until=moment + timedelta(days=1),
            )
            db.add(mandate)
            db.flush()
            _event(db, mandate, "cycle_started", {"test": True})
            _event(
                db,
                mandate,
                "ungrounded_discovery_recovered_by_operator",
                {"test": True},
            )
            db.commit()
            events = db.scalars(
                select(AlphaDiscoveryEvent).order_by(AlphaDiscoveryEvent.sequence)
            ).all()
            assert [event.sequence for event in events] == [1, 2]
            assert events[1].previous_digest == events[0].event_digest
            assert events[1].event_digest != events[0].event_digest
    finally:
        engine.dispose()
