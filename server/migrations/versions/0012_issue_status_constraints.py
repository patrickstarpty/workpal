"""Add status contract without rewriting catalog values."""
from alembic import op
import sqlalchemy as sa
revision = '0012'
down_revision = '0011'
branch_labels = depends_on = None


def upgrade():
    # sqlite3 legacy transaction mode does not begin on DDL. Ensure copy/drop,
    # index creation and Alembic revision update share an atomic transaction.
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite' and not bind.connection.driver_connection.in_transaction:
        bind.exec_driver_sql('BEGIN')
    with op.batch_alter_table('issue_status', recreate='always', table_args=(sa.CheckConstraint('is_system IN (0,1)'), sa.CheckConstraint("category IN ('unstarted','started','done','closed')"))) as batch:
        batch.add_column(sa.Column('icon', sa.String(), nullable=False, server_default=''))
        batch.alter_column('description', existing_type=sa.String(), server_default='')
        batch.alter_column('is_system', existing_type=sa.Boolean(), server_default='0')
        batch.alter_column('position', existing_type=sa.Integer(), type_=sa.Float(), server_default='0')
        batch.create_check_constraint("issue_status_contract_0", "length(key) BETWEEN 1 AND 32 AND key NOT GLOB '*[^a-z0-9_]*' AND substr(key,1,1) GLOB '[a-z0-9]'")
        batch.create_check_constraint("issue_status_contract_1", 'length(name) BETWEEN 1 AND 64')
        batch.create_check_constraint("issue_status_contract_2", 'length(description) <= 256')
        batch.create_check_constraint("issue_status_contract_3", "length(color) = 7 AND substr(color,1,1) = '#' AND substr(color,2) NOT GLOB '*[^0-9a-f]*'")
        batch.create_check_constraint("issue_status_contract_4", "NOT is_system OR ((key = 'backlog' AND category = 'unstarted') OR (key = 'todo' AND category = 'unstarted') OR (key = 'in_progress' AND category = 'started') OR (key = 'in_review' AND category = 'started') OR (key = 'blocked' AND category = 'started') OR (key = 'done' AND category = 'done') OR (key = 'cancelled' AND category = 'closed'))")
        batch.create_check_constraint("issue_status_contract_5", 'NOT is_system OR archived_at IS NULL')
    op.create_index('idx_issue_status_workspace_name_active', 'issue_status', ['workspace_id', sa.text('lower(name)')], unique=True, sqlite_where=sa.text('archived_at IS NULL'))


def downgrade():
    raise RuntimeError('Status contract downgrade requires explicit data review')
