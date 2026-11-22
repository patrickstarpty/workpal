"""Canonical activity records, initially for issue-independent audit events.

The issue domain is not migrated yet. Reject non-null issue_id until its
canonical foreign key can be installed, instead of accepting dangling records.
"""
from alembic import op
import sqlalchemy as sa
revision='0017'
down_revision='0016'
branch_labels=depends_on=None


def upgrade():
    op.create_table('activity_log',
        sa.Column('id',sa.Text(),primary_key=True,server_default=sa.text('(workpal_uuid())')),
        sa.Column('workspace_id',sa.Text(),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
        sa.Column('issue_id',sa.Text()),
        sa.Column('actor_type',sa.Text()),sa.Column('actor_id',sa.Text()),
        sa.Column('action',sa.Text(),nullable=False),
        sa.Column('details',sa.Text(),nullable=False,server_default='{}'),
        sa.Column('created_at',sa.Text(),nullable=False,server_default=sa.text('(workpal_now())')),
        sa.CheckConstraint("actor_type IN ('member','agent','system')"),
        sa.CheckConstraint('workpal_jsonb_valid(details)=1'),
        sa.CheckConstraint('instr(action,char(0))=0'),
        sa.CheckConstraint('issue_id IS NULL',name='activity_issue_domain_pending'))
    op.execute('CREATE INDEX idx_activity_log_issue_keyset ON activity_log(issue_id,created_at DESC,id DESC)')
    op.execute("""CREATE INDEX idx_activity_log_member_assignee_frequency ON activity_log
        (workspace_id,actor_id,json_extract(details,'$.to_type'),json_extract(details,'$.to_id'))
        WHERE actor_type='member' AND action='assignee_changed' AND json_extract(details,'$.to_type') IS NOT NULL
        AND json_extract(details,'$.to_id') IS NOT NULL""")
    op.execute("""CREATE INDEX idx_activity_log_squad_no_action_task ON activity_log
        (issue_id,actor_id,json_extract(details,'$.task_id')) WHERE actor_type='agent'
        AND action='squad_leader_evaluated' AND json_extract(details,'$.outcome')='no_action'""")


def downgrade():
    raise RuntimeError('Activity audit downgrade requires explicit data review')
