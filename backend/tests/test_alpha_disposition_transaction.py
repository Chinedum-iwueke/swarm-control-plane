"""Disposable PostgreSQL only: prove concurrent and same-transaction deduplication."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.alpha_discovery import AlphaDiscoveryEvent, AlphaResearchMandate
from app.services.alpha_disposition import retain_disposition


def test_recovery_ledger_serializes_duplicate_deliveries():
    url = os.environ.get("AEP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set AEP_TEST_DATABASE_URL for disposable PostgreSQL validation")
    assert url.startswith("postgresql+psycopg://") and url.endswith("/hermes_discovery_test")
    engine = create_engine(url, connect_args={"options": "-c statement_timeout=10000 -c search_path=aep002"})
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE SCHEMA aep002")
            conn.exec_driver_sql("CREATE TABLE alpha_discovery_cycles (id uuid PRIMARY KEY)")
            AlphaResearchMandate.__table__.create(conn)
            AlphaDiscoveryEvent.__table__.create(conn)
        with Session(engine, autoflush=False) as db:
            moment = datetime.now(UTC)
            mandate = AlphaResearchMandate(mandate_key="aep002-test", version="1.0.0",
                objective="No production work", specification={}, budget={}, mandate_digest="a"*64,
                created_by="test", valid_from=moment, valid_until=moment+timedelta(days=1))
            db.add(mandate)
            db.commit()
            identity = mandate.id
        barrier = Barrier(2)
        def deliver():
            with Session(engine, autoflush=False) as db:
                mandate = db.get(AlphaResearchMandate, identity)
                barrier.wait(timeout=10)
                first = retain_disposition(db, mandate, "scientific_requirements_rejected", {"subject": "frozen"})
                second = retain_disposition(db, mandate, "scientific_requirements_rejected", {"subject": "frozen"})
                assert first == second
                db.commit()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(deliver) for _ in range(2)]
            for future in futures:
                future.result(timeout=30)
        with Session(engine, autoflush=False) as db:
            assert len(db.scalars(select(AlphaDiscoveryEvent)).all()) == 1
            mandate = db.get(AlphaResearchMandate, identity)
            retain_disposition(db, mandate, "scientific_requirements_rejected", {"subject": "changed"})
            db.commit()
            events = db.scalars(select(AlphaDiscoveryEvent).order_by(AlphaDiscoveryEvent.sequence)).all()
            assert len(events) == 2
            assert events[1].previous_digest == events[0].event_digest
    finally:
        engine.dispose()
