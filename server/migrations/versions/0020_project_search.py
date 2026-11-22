"""Canonical project storage and durable search-change trigger records.

SQLite search planning is separate from PostgreSQL GIN/trigram opclasses.
Transaction counter rollback gaps and full snapshot/concurrency protocol gates
remain explicit verification obligations, not a completed search API.
"""
from alembic import op
import sqlalchemy as sa
revision='0020'
down_revision='0019'
branch_labels=depends_on=None


def upgrade():
    op.create_table('workpal_transaction_clock',
        sa.Column('singleton',sa.Integer(),primary_key=True),sa.Column('value',sa.Integer(),nullable=False),
        sa.CheckConstraint('singleton=1'),sa.CheckConstraint('value>=2'))
    op.execute('INSERT INTO workpal_transaction_clock(singleton,value) VALUES (1,2)')
    op.create_table('search_index_change',
        sa.Column('entity_type',sa.Text(),primary_key=True),sa.Column('entity_id',sa.Text(),primary_key=True),
        sa.Column('workspace_id',sa.Text(),nullable=False),sa.Column('change_xid',sa.Integer(),nullable=False),
        sa.Column('changed_at',sa.Text(),nullable=False,server_default=sa.text('(workpal_now())')),
        sa.CheckConstraint("entity_type IN ('issue','comment','project')"),sa.CheckConstraint("typeof(change_xid)='integer' AND change_xid>=0"))
    op.create_index('idx_search_index_change_changed_at','search_index_change',['changed_at'])
    op.create_index('idx_search_index_change_workspace_xid','search_index_change',['workspace_id','change_xid','entity_type','entity_id'])
    op.create_table('search_index_prune_mark',
        sa.Column('singleton',sa.Boolean(create_constraint=True),primary_key=True,server_default=sa.true()),
        sa.Column('pruned_through_xid',sa.Integer(),nullable=False),
        sa.CheckConstraint('singleton=1'),sa.CheckConstraint("typeof(pruned_through_xid)='integer' AND pruned_through_xid>=0"))
    op.create_table('project',
        sa.Column('id',sa.Text(),primary_key=True,server_default=sa.text('(workpal_uuid())')),
        sa.Column('workspace_id',sa.Text(),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
        sa.Column('title',sa.Text(),nullable=False),sa.Column('description',sa.Text()),sa.Column('icon',sa.Text()),
        sa.Column('status',sa.Text(),nullable=False,server_default='planned'),
        sa.Column('lead_type',sa.Text()),sa.Column('lead_id',sa.Text()),
        sa.Column('created_at',sa.Text(),nullable=False,server_default=sa.text('(workpal_now())')),
        sa.Column('updated_at',sa.Text(),nullable=False,server_default=sa.text('(workpal_now())')),
        sa.Column('priority',sa.Text(),nullable=False,server_default='none'),
        sa.Column('start_date',sa.Text()),sa.Column('due_date',sa.Text()),sa.Column('workflow_id',sa.Text()),
        sa.Column('creator_type',sa.Text()),sa.Column('creator_id',sa.Text()),
        sa.Column('visibility',sa.Text(),nullable=False,server_default='workspace'),
        sa.Column('archived_at',sa.Text()),sa.Column('archived_by_type',sa.Text()),sa.Column('archived_by_id',sa.Text()),
        sa.Column('folder_id',sa.Text()),
        sa.CheckConstraint("lead_type IN ('member','agent')",name='project_lead_type_check'),
        sa.CheckConstraint("priority IN ('urgent','high','medium','low','none')",name='project_priority_check'),
        sa.CheckConstraint("status IN ('planned','in_progress','paused','completed','cancelled')",name='project_status_check'),
        *[sa.CheckConstraint(f'{name} IS NULL OR instr({name},char(0))=0') for name in
          ('title','description','icon','creator_type','visibility','archived_by_type')])
    op.create_index('idx_project_workspace','project',['workspace_id'])
    # Expression indexes support the normalized-text seam; they do not claim
    # PostgreSQL trigram search acceleration or operator semantics.
    op.execute('CREATE INDEX idx_project_title_trgm ON project(lower(title))')
    op.execute("CREATE INDEX idx_project_description_trgm ON project(lower(COALESCE(description,'')))")
    for operation,record in [('INSERT','NEW'),('UPDATE','NEW'),('DELETE','OLD')]:
        op.execute(f'''CREATE TRIGGER trg_project_search_index_change_{operation.lower()}
            AFTER {operation} ON project WHEN workpal_setting('workpal.workspace_teardown') IS NOT 'on'
            BEGIN
                INSERT INTO search_index_change(entity_type,entity_id,workspace_id,change_xid,changed_at)
                VALUES ('project',{record}.id,{record}.workspace_id,workpal_xid(),workpal_now())
                ON CONFLICT(entity_type,entity_id) DO UPDATE SET workspace_id=excluded.workspace_id,
                    change_xid=excluded.change_xid,changed_at=excluded.changed_at;
            END''')


def downgrade():
    raise RuntimeError('Project/search downgrade requires explicit data review')
