from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.risk_rules import router
from app.schemas.risk_rules import (
    RiskRuleEvaluationCreate,
    RiskRuleRequest,
    VenueRulePack,
)
from app.services.research import record_digest
from app.services.risk_rules import RiskRuleConflict, build_receipt, register_evaluation
from pydantic import ValidationError

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)
REFERENCE_ID = uuid4()
STRESS_ID = uuid4()


def snapshot():
    temporal = {
        "valid_from": (NOW - timedelta(days=100)).isoformat(),
        "valid_to": None,
        "observed_at": (NOW - timedelta(days=2)).isoformat(),
        "available_at": (NOW - timedelta(days=2)).isoformat(),
    }
    return {
        "schema_version": 1,
        "as_of": (NOW - timedelta(days=1)).isoformat(),
        "source": "exchange-rules",
        "source_revision": "r1",
        "venues": [
            {
                **temporal,
                "revision_id": "venue-r1",
                "corrects_revision_id": None,
                "venue_id": "bybit",
                "name": "Bybit",
                "mic": None,
                "timezone": "UTC",
                "calendar_id": "always",
            }
        ],
        "instruments": [
            {
                **temporal,
                "revision_id": "instrument-r1",
                "corrects_revision_id": None,
                "instrument_id": "BTCUSDT-PERP",
                "asset_class": "crypto_perpetual",
                "base_asset": "BTC",
                "quote_asset": "USDT",
                "settlement_asset": "USDT",
                "contract_type": "perpetual",
                "expiry_at": None,
            }
        ],
        "listings": [
            {
                **temporal,
                "valid_from": "2024-01-01T00:00:00+00:00",
                "valid_to": temporal["valid_from"],
                "observed_at": "2023-12-31T00:00:00+00:00",
                "available_at": "2023-12-31T00:00:00+00:00",
                "revision_id": "listing-old",
                "corrects_revision_id": None,
                "listing_id": "bybit-BTCUSDT",
                "instrument_id": "BTCUSDT-PERP",
                "venue_id": "bybit",
                "symbol": "BTCUSDT-OLD",
                "status": "active",
                "price_increment": 0.1,
                "quantity_increment": 0.001,
                "contract_multiplier": 1.0,
            },
            {
                **temporal,
                "revision_id": "listing-r1",
                "corrects_revision_id": None,
                "listing_id": "bybit-BTCUSDT",
                "instrument_id": "BTCUSDT-PERP",
                "venue_id": "bybit",
                "symbol": "BTCUSDT",
                "status": "active",
                "price_increment": 0.1,
                "quantity_increment": 0.001,
                "contract_multiplier": 1.0,
            },
        ],
        "calendars": [
            {
                **temporal,
                "revision_id": "calendar-r1",
                "corrects_revision_id": None,
                "calendar_id": "always",
                "timezone": "UTC",
                "sessions": [
                    {"weekday": day, "opens_at": "00:00:00", "closes_at": "00:00:00"}
                    for day in range(7)
                ],
                "holidays": [],
            }
        ],
        "corporate_actions": [],
    }


def rule_pack():
    return {
        "schema_version": "venue-risk-rule-pack-v1.0.0",
        "venue_id": "bybit",
        "instrument_id": "BTCUSDT-PERP",
        "listing_id": "bybit-BTCUSDT",
        "version": "v1",
        "source_uri": "https://bybit.example/rules",
        "source_digest": record_digest({"source": "rules"}),
        "observed_at": NOW - timedelta(hours=2),
        "available_at": NOW - timedelta(hours=1),
        "effective_from": NOW - timedelta(minutes=30),
        "effective_to": None,
        "status": "active",
        "transition": "activate",
        "supersedes_rule_pack_digest": None,
        "margin_tiers": [
            {
                "tier": 1,
                "notional_floor": 0,
                "notional_cap": 100000,
                "maximum_leverage": 10,
                "maintenance_margin_rate": 0.005,
                "maintenance_amount": 0,
            },
            {
                "tier": 2,
                "notional_floor": 100000,
                "notional_cap": 500000,
                "maximum_leverage": 5,
                "maintenance_margin_rate": 0.01,
                "maintenance_amount": 500,
            },
        ],
        "price_increment": 0.1,
        "quantity_increment": 0.001,
        "maximum_mark_deviation": 0.02,
        "maximum_abs_funding_rate": 0.001,
        "minimum_liquidation_buffer": 100,
    }


def request_value():
    pack = VenueRulePack.model_validate(rule_pack())
    return {
        "schema_version": "risk-rule-evaluation-request-v1.0.0",
        "reference_snapshot_id": REFERENCE_ID,
        "reference_snapshot_digest": record_digest(snapshot()),
        "risk_stress_assessment_id": STRESS_ID,
        "risk_stress_dossier_digest": record_digest({"risk": "admissible"}),
        "rule_pack": pack.model_dump(mode="json"),
        "rule_pack_digest": record_digest(pack),
        "position": {
            "side": "long",
            "quantity": 1.0,
            "entry_price": 50000.0,
            "mark_price": 50500.0,
            "index_price": 50400.0,
            "collateral": 10000.0,
            "requested_leverage": 5.0,
            "accrued_funding": 10.0,
            "fee_reserve": 25.0,
            "state_digest": record_digest({"position": "long"}),
        },
        "evaluated_at": NOW,
        "maximum_rule_age_seconds": 7200,
        "allocation_authority": False,
        "order_authority": False,
        "capital_authority": False,
    }


def payload(value=None):
    request = RiskRuleRequest.model_validate(value or request_value())
    return RiskRuleEvaluationCreate.model_validate(
        {
            "evaluation_key": "RISK002-PILOT",
            "request": request,
            "request_digest": record_digest(request),
            "evaluated_by": "risk002-pilot",
        }
    )


def dependencies(stress_decision="admissible"):
    snap = snapshot()
    return SimpleNamespace(
        id=REFERENCE_ID, snapshot=snap, snapshot_digest=record_digest(snap)
    ), SimpleNamespace(
        id=STRESS_ID,
        dossier_digest=record_digest({"risk": "admissible"}),
        decision=stress_decision,
    )


def test_valid_position_is_allowed_without_authority():
    receipt, decision = build_receipt(payload(), *dependencies())
    assert decision == "allowed"
    assert receipt["selected_margin_tier"] == 1
    assert receipt["liquidation_buffer"] == "10212.50000"
    assert receipt["capital_authority"] is False


@pytest.mark.parametrize(
    "mutation,failure",
    [
        (
            lambda v: v["position"].update(requested_leverage=11.0),
            "leverage_limit_breached",
        ),
        (
            lambda v: v["position"].update(quantity=0.9995),
            "quantity_increment_violation",
        ),
        (
            lambda v: v["position"].update(entry_price=50000.05),
            "price_increment_violation",
        ),
        (
            lambda v: v["position"].update(mark_price=52000.0),
            "mark_price_deviation_breached",
        ),
        (
            lambda v: v["position"].update(accrued_funding=100.0),
            "funding_limit_breached",
        ),
        (
            lambda v: v["position"].update(
                collateral=100.0, mark_price=49500.0, index_price=49500.0
            ),
            "liquidation_buffer_breached",
        ),
    ],
)
def test_hard_boundaries_deny(mutation, failure):
    value = request_value()
    mutation(value)
    receipt, decision = build_receipt(payload(value), *dependencies())
    assert decision == "denied" and failure in receipt["failures"]


@pytest.mark.parametrize(
    "change,failure",
    [
        ("stale", "stale_rule_pack"),
        ("future", "rule_not_yet_known"),
        ("suspended", "rule_pack_not_active"),
        ("expired", "rule_not_effective"),
    ],
)
def test_unknown_or_inactive_rule_state_fails_closed(change, failure):
    value = request_value()
    if change == "stale":
        value["maximum_rule_age_seconds"] = 1
    elif change == "future":
        value["rule_pack"]["available_at"] = (NOW + timedelta(minutes=1)).isoformat()
    elif change == "suspended":
        value["rule_pack"].update(
            status="suspended",
            transition="suspend",
            supersedes_rule_pack_digest="1" * 64,
        )
    else:
        value["rule_pack"]["effective_to"] = (NOW - timedelta(minutes=1)).isoformat()
    pack = VenueRulePack.model_validate(value["rule_pack"])
    value["rule_pack"] = pack.model_dump(mode="json")
    value["rule_pack_digest"] = record_digest(pack)
    receipt, decision = build_receipt(payload(value), *dependencies())
    assert decision == "denied" and failure in receipt["failures"]


def test_dependency_and_digest_drift_are_rejected():
    with pytest.raises(RiskRuleConflict, match="admissible"):
        build_receipt(payload(), *dependencies(stress_decision="blocked"))
    bad = payload().model_copy(update={"request_digest": "0" * 64})
    with pytest.raises(RiskRuleConflict, match="digest"):
        build_receipt(bad, *dependencies())


def test_invalid_margin_tiers_and_transition_are_rejected():
    value = rule_pack()
    value["margin_tiers"][1]["notional_floor"] = 90000
    with pytest.raises(ValidationError, match="without gaps"):
        VenueRulePack.model_validate(value)
    value = rule_pack()
    value["transition"] = "amend"
    with pytest.raises(ValidationError, match="predecessor"):
        VenueRulePack.model_validate(value)


def test_registration_is_idempotent_and_routes_are_protected():
    db = MagicMock()
    reference, stress = dependencies()
    db.get.side_effect = [reference, stress]
    db.scalar.return_value = None
    first = register_evaluation(db, payload())
    assert first.request_digest == payload().request_digest
    db.get.side_effect = [reference, stress]
    db.scalar.return_value = first
    assert register_evaluation(db, payload()) is first
    assert router.dependencies
