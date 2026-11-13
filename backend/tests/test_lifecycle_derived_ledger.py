import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


def migration_sql():
    path = Path(__file__).parents[1] / "alembic/versions/d0a2b5f83c71_track_lifecycle_derived_changes.py"
    spec = importlib.util.spec_from_file_location("lifecycle_ledger_migration", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", {"alembic": MagicMock()}):
        spec.loader.exec_module(module)
    module.op = MagicMock()
    module.upgrade()
    return [call.args[0] for call in module.op.execute.call_args_list]


def test_lifecycle_migration_covers_both_successors_and_preserves_epoch_order():
    sql = "\n".join(migration_sql())
    assert "OLD.successor_object_id" in sql and "NEW.successor_object_id" in sql
    assert "epoch + 1" in sql
    assert "FOR EACH ROW" in sql
    assert "AFTER INSERT OR UPDATE OR DELETE" in sql


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TRIGGER_TESTS") != "1", reason="explicit isolated Docker PostgreSQL test")
def test_lifecycle_ledger_trigger_on_real_postgres():
    name = "invariance-derived-ledger-test-" + uuid4().hex[:12]
    def docker(*args, **kwargs):
        return subprocess.run(["sudo", "-n", "docker", *args], check=True, capture_output=True, text=True, timeout=60, **kwargs)
    docker("run", "--rm", "-d", "--name", name, "--network", "none", "--cpus", "1", "--memory", "256m",
           "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:16-alpine")
    try:
        for _ in range(30):
            try:
                docker("exec", name, "pg_isready", "-U", "postgres")
                break
            except subprocess.CalledProcessError:
                time.sleep(1)
        def sql(statement):
            return docker("exec", "-i", name, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-Atq", input=statement).stdout.strip()
        sql("""
            CREATE TABLE canonical_evidence_objects(id uuid PRIMARY KEY, project text);
            CREATE TABLE evidence_lifecycle_states(object_id uuid PRIMARY KEY, successor_object_id uuid, state text);
            CREATE TABLE evidence_corpus_freshness(corpus_name text PRIMARY KEY, epoch bigint);
            INSERT INTO evidence_corpus_freshness VALUES('canonical-scientific',20);
            CREATE TABLE derived_state_changes(source_epoch bigint,entity_kind text,entity_id text,mutation text,
                project text,affected_object_ids jsonb,transaction_id bigint);
            CREATE FUNCTION bump_test_epoch() RETURNS trigger AS $$ BEGIN
                UPDATE evidence_corpus_freshness SET epoch=epoch+1;
                RETURN NULL; END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER trg_evidence_lifecycle_states_freshness
                AFTER INSERT OR UPDATE OR DELETE ON evidence_lifecycle_states
                FOR EACH STATEMENT EXECUTE FUNCTION bump_test_epoch();
        """)
        for statement in migration_sql():
            sql(statement)
        a,b,c = [str(uuid4()) for _ in range(3)]
        sql(f"INSERT INTO canonical_evidence_objects VALUES ('{a}','research'),('{b}','research'),('{c}','research');")
        sql(f"INSERT INTO evidence_lifecycle_states VALUES ('{a}',NULL,'active'),('{b}',NULL,'active');")
        assert sql("SELECT epoch FROM evidence_corpus_freshness") == "21"
        assert sql("SELECT count(*) FROM derived_state_changes WHERE source_epoch=21") == "2"
        sql(f"UPDATE evidence_lifecycle_states SET successor_object_id='{b}',state='superseded' WHERE object_id='{a}';")
        sql(f"UPDATE evidence_lifecycle_states SET successor_object_id='{c}' WHERE object_id='{a}';")
        ids = json.loads(sql("SELECT affected_object_ids FROM derived_state_changes WHERE source_epoch=23"))
        assert set(ids) == {a,b,c}
        sql(f"DELETE FROM evidence_lifecycle_states WHERE object_id='{a}';")
        assert json.loads(sql("SELECT affected_object_ids FROM derived_state_changes WHERE source_epoch=24")) == [a,c]
        sql(f"BEGIN; UPDATE evidence_lifecycle_states SET state='deleted' WHERE object_id='{b}'; ROLLBACK;")
        assert sql("SELECT epoch FROM evidence_corpus_freshness") == "24"
        assert sql("SELECT count(*) FROM derived_state_changes WHERE source_epoch>24") == "0"
        assert sql("SELECT count(DISTINCT source_epoch) FROM derived_state_changes") == "4"
    finally:
        docker("stop", name)
