from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.api.routes.agent_research import _require_role
from fastapi import HTTPException


def test_role_endpoint_requires_agent_capability() -> None:
    agent = SimpleNamespace(id="agent", capabilities=[])
    with pytest.raises(HTTPException, match="lacks required capability"):
        _require_role(
            MagicMock(),
            agent,
            capability="statistical-review",
            package_name="m13-statistical-reviewer",
        )


def test_role_endpoint_requires_matching_active_package() -> None:
    agent = SimpleNamespace(id="agent", capabilities=["statistical-review"])
    db = MagicMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException, match="not actively deployed"):
        _require_role(
            db,
            agent,
            capability="statistical-review",
            package_name="m13-statistical-reviewer",
        )


def test_role_endpoint_accepts_capability_from_matching_package() -> None:
    agent = SimpleNamespace(id="agent", capabilities=["statistical-review"])
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(
        manifest={"required_capabilities": ["statistical-review"]}
    )
    _require_role(
        db,
        agent,
        capability="statistical-review",
        package_name="m13-statistical-reviewer",
    )
