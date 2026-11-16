from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from app.api.routes.tasks import list_tasks


def test_history_uses_durable_lease_participation_without_duplicate_rows():
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    agent_id = uuid4()
    list_tasks(db, participating_agent_id=agent_id)
    statement = db.scalars.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "EXISTS" in sql
    assert "task_events.agent_id" in sql
    assert "task_leased" in sql
    assert " OR " in sql
    assert str(agent_id) in sql
    assert "JOIN" not in sql


def test_current_query_remains_assignment_only_and_active():
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    list_tasks(db, assigned_agent_id=uuid4(), active_only=True)
    sql = str(db.scalars.call_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "task_events" not in sql
    assert "leased" in sql and "running" in sql
