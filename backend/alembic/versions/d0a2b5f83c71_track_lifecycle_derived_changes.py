"""Track lifecycle epochs in the derived-state change ledger.

Revision ID: d0a2b5f83c71
Revises: c9f1a4e72b60
"""
from alembic import op

revision = "d0a2b5f83c71"
down_revision = "c9f1a4e72b60"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION record_lifecycle_derived_state_change()
        RETURNS trigger AS $$
        DECLARE
            affected_id uuid;
            affected_ids jsonb;
            project_value text;
            next_epoch bigint;
        BEGIN
            IF TG_OP = 'DELETE' THEN affected_id := OLD.object_id;
            ELSE affected_id := NEW.object_id; END IF;
            affected_ids := jsonb_build_array(affected_id::text);
            IF TG_OP <> 'INSERT' THEN
                IF OLD.successor_object_id IS NOT NULL THEN
                    affected_ids := affected_ids || jsonb_build_array(OLD.successor_object_id::text);
                END IF;
            END IF;
            IF TG_OP <> 'DELETE' THEN
                IF NEW.successor_object_id IS NOT NULL THEN
                    affected_ids := affected_ids || jsonb_build_array(NEW.successor_object_id::text);
                END IF;
            END IF;
            SELECT project INTO project_value FROM canonical_evidence_objects WHERE id = affected_id;
            -- Row triggers run before the existing statement-level epoch bump.
            SELECT epoch + 1 INTO next_epoch FROM evidence_corpus_freshness
            WHERE corpus_name = 'canonical-scientific';
            INSERT INTO derived_state_changes
                (source_epoch, entity_kind, entity_id, mutation, project,
                 affected_object_ids, transaction_id)
            VALUES
                (COALESCE(next_epoch, 0), TG_TABLE_NAME, affected_id::text, lower(TG_OP),
                 COALESCE(project_value, '*'), affected_ids, txid_current());
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_evidence_lifecycle_states_derived_state_change
        AFTER INSERT OR UPDATE OR DELETE ON evidence_lifecycle_states
        FOR EACH ROW EXECUTE FUNCTION record_lifecycle_derived_state_change()
    """)


def downgrade():
    op.execute("DROP TRIGGER trg_evidence_lifecycle_states_derived_state_change ON evidence_lifecycle_states")
    op.execute("DROP FUNCTION record_lifecycle_derived_state_change()")
