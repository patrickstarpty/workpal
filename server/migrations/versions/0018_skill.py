"""Canonical skills and agent assignments from the frozen Go schema catalog."""
from alembic import op
import sqlalchemy as sa
revision='0018'
down_revision='0017'
branch_labels=depends_on=None


def upgrade():
    op.create_table('skill',
        sa.Column('id',sa.Text(),primary_key=True,server_default=sa.text('(workpal_uuid())')),
        sa.Column('workspace_id',sa.Text(),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
        sa.Column('name',sa.Text(),nullable=False),
        sa.Column('description',sa.Text(),nullable=False,server_default=''),
        sa.Column('content',sa.Text(),nullable=False,server_default=''),
        sa.Column('config',sa.Text(),nullable=False,server_default='{}'),
        sa.Column('created_by',sa.Text(),sa.ForeignKey('users.id')),
        sa.Column('created_at',sa.Text(),nullable=False,server_default=sa.text('(workpal_now())')),
        sa.Column('updated_at',sa.Text(),nullable=False,server_default=sa.text('(workpal_now())')),
        # Go deliberately has no plugin installation foreign key here.
        sa.Column('plugin_installation_id',sa.Text()),
        sa.UniqueConstraint('workspace_id','name',name='skill_workspace_id_name_key'),
        sa.CheckConstraint('workpal_jsonb_valid(config)=1'),
        *[sa.CheckConstraint(f'instr({name},char(0))=0') for name in ('name','description','content')])
    op.create_index('idx_skill_workspace','skill',['workspace_id'])
    op.create_table('agent_skill',
        sa.Column('agent_id',sa.Text(),sa.ForeignKey('agent.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('skill_id',sa.Text(),sa.ForeignKey('skill.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('created_at',sa.Text(),nullable=False,server_default=sa.text('(workpal_now())')),
        sa.Column('enabled',sa.Boolean(create_constraint=True),nullable=False,server_default=sa.true()))
    op.create_index('idx_agent_skill_agent','agent_skill',['agent_id'])
    op.create_index('idx_agent_skill_skill','agent_skill',['skill_id'])


def downgrade():
    raise RuntimeError('Canonical skill downgrade requires explicit data review')
