"""Canonical chat sessions, including attachment-owner dependency relationships."""
from alembic import op
import sqlalchemy as sa
revision='0019'
down_revision='0018'
branch_labels=depends_on=None


def upgrade():
    op.create_table('chat_session',
        sa.Column('id',sa.Text(),primary_key=True,server_default=sa.text('(workpal_uuid())')),
        sa.Column('workspace_id',sa.Text(),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
        sa.Column('agent_id',sa.Text(),sa.ForeignKey('agent.id',ondelete='CASCADE'),nullable=False),
        sa.Column('creator_id',sa.Text(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('title',sa.Text(),nullable=False,server_default=''),
        sa.Column('session_id',sa.Text()),sa.Column('work_dir',sa.Text()),
        sa.Column('status',sa.Text(),nullable=False,server_default='active'),
        sa.Column('created_at',sa.Text(),nullable=False,server_default=sa.text('(workpal_now())')),
        sa.Column('updated_at',sa.Text(),nullable=False,server_default=sa.text('(workpal_now())')),
        sa.Column('unread_since',sa.Text()),
        sa.Column('runtime_id',sa.Text(),sa.ForeignKey('agent_runtime.id',ondelete='SET NULL')),
        sa.Column('last_read_at',sa.Text(),nullable=False,server_default=sa.text('(workpal_now())')),
        sa.Column('is_agent_intro',sa.Boolean(create_constraint=True),nullable=False,server_default=sa.false()),
        sa.Column('pinned_at',sa.Text()),sa.Column('project_id',sa.Text()),
        sa.Column('explicitly_created_at',sa.Text()),
        sa.CheckConstraint("status IN ('active','archived')",name='chat_session_status_check'),
        *[sa.CheckConstraint(f'{name} IS NULL OR instr({name},char(0))=0') for name in ('title','session_id','work_dir')])
    for name,columns,where in [
        ('idx_chat_session_agent_id',['agent_id'],None),
        ('idx_chat_session_creator',['creator_id','workspace_id'],None),
        ('idx_chat_session_project',['project_id'],'project_id IS NOT NULL'),
        ('idx_chat_session_runtime_id',['runtime_id'],'runtime_id IS NOT NULL'),
        ('idx_chat_session_workspace',['workspace_id'],None)]:
        op.create_index(name,'chat_session',columns,sqlite_where=sa.text(where) if where else None)
    op.execute('CREATE INDEX idx_chat_session_pinned ON chat_session(creator_id,workspace_id,pinned_at DESC) WHERE pinned_at IS NOT NULL')


def downgrade():
    raise RuntimeError('Canonical chat session downgrade requires explicit data review')
