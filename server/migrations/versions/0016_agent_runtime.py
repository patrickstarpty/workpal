"""Canonical agent/runtime schema from the frozen Go migration catalog.

Legacy workspace_records remain untouched; conversion is a separate gate.
"""
from alembic import op
import sqlalchemy as sa

revision='0016'
down_revision='0015'
branch_labels=depends_on=None


def identity():
    return sa.Column('id',sa.Text(),primary_key=True,server_default=sa.text('(workpal_uuid())'))


def stamp(name):
    return sa.Column(name,sa.Text(),nullable=False,server_default=sa.text('(workpal_now())'))


def field(name,nullable=True,default=None,foreign=None):
    args=[name,sa.Text()]
    if foreign:args.append(sa.ForeignKey(foreign))
    return sa.Column(*args,nullable=nullable,server_default=default)


def json_field(name,default=None):
    return field(name,nullable=default is None,default=default)


def checks(strings,jsons,arrays=()):
    return ([sa.CheckConstraint(f"{name} IS NULL OR instr({name},char(0))=0") for name in strings]
        +[sa.CheckConstraint(f"{name} IS NULL OR workpal_jsonb_valid({name})=1") for name in jsons]
        +[sa.CheckConstraint(f"{name} IS NULL OR workpal_array_valid({name},'{kind}')=1") for name,kind in arrays])


def upgrade():
    op.create_table('agent_runtime',identity(),
        sa.Column('workspace_id',sa.Text(),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
        field('daemon_id'),field('name',False),field('runtime_mode',False),field('provider',False),
        field('status',False,'offline'),field('device_info',False,''),json_field('metadata','{}'),
        field('last_seen_at'),stamp('created_at'),stamp('updated_at'),field('owner_id',foreign='users.id'),
        field('legacy_daemon_id'),field('visibility',False,'private'),field('profile_id'),field('custom_name'),
        field('shared_with',False,'[]'),sa.Column('max_concurrent_tasks',sa.Integer()),
        sa.CheckConstraint("max_concurrent_tasks IS NULL OR (typeof(max_concurrent_tasks)='integer' AND max_concurrent_tasks BETWEEN -2147483648 AND 2147483647)"),
        sa.CheckConstraint("runtime_mode IN ('local','cloud')"),
        sa.CheckConstraint("status IN ('online','offline')"),
        sa.CheckConstraint("visibility IN ('private','public')"),
        *checks(['daemon_id','name','provider','device_info','legacy_daemon_id','custom_name'],
                ['metadata'],[('shared_with','uuid')]))
    op.create_index('agent_runtime_workspace_daemon_profile_key','agent_runtime',
        ['workspace_id','daemon_id','profile_id'],unique=True,sqlite_where=sa.text('profile_id IS NOT NULL'))
    op.create_index('agent_runtime_workspace_daemon_provider_key','agent_runtime',
        ['workspace_id','daemon_id','provider'],unique=True,sqlite_where=sa.text('profile_id IS NULL'))
    for name,columns,predicate in [
        ('idx_agent_runtime_offline_last_seen',['last_seen_at','id'],"status='offline'"),
        ('idx_agent_runtime_online_last_seen',['last_seen_at'],"status='online'"),
        ('idx_agent_runtime_status',['workspace_id','status'],None),
        ('idx_agent_runtime_workspace',['workspace_id'],None),
        ('idx_agent_runtime_workspace_id_keyset',['workspace_id','id'],None)]:
        op.create_index(name,'agent_runtime',columns,sqlite_where=sa.text(predicate) if predicate else None)
    op.create_table('agent',identity(),
        sa.Column('workspace_id',sa.Text(),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
        field('name',False),field('avatar_url'),field('runtime_mode',False),
        json_field('runtime_config','{}'),field('visibility',False,'private'),
        field('status',False,'offline'),
        sa.Column('max_concurrent_tasks',sa.Integer(),nullable=False,server_default='6'),
        field('owner_id',foreign='users.id'),stamp('created_at'),stamp('updated_at'),
        field('description',False,''),
        sa.Column('runtime_id',sa.Text(),sa.ForeignKey('agent_runtime.id',ondelete='RESTRICT')),
        field('instructions',False,''),field('archived_at'),field('archived_by',foreign='users.id'),
        json_field('custom_env','{}'),json_field('custom_args','[]'),json_field('mcp_config'),
        field('model'),field('thinking_level'),field('composio_toolkit_allowlist'),
        field('permission_mode',False,'private'),field('kind',False,'user'),field('system_key'),
        json_field('disabled_runtime_skills','[]'),field('service_tier'),json_field('conversation_starters','[]'),
        sa.CheckConstraint("max_concurrent_tasks IS NULL OR (typeof(max_concurrent_tasks)='integer' AND max_concurrent_tasks BETWEEN -2147483648 AND 2147483647)"),
        sa.CheckConstraint("runtime_mode IN ('local','cloud')"),
        sa.CheckConstraint("visibility IN ('workspace','private')"),
        sa.CheckConstraint("status IN ('idle','working','blocked','error','offline')"),
        sa.CheckConstraint("permission_mode IN ('private','public_to')"),
        sa.CheckConstraint("kind IN ('user','system')"),
        sa.CheckConstraint('length(description)<=255'),
        sa.CheckConstraint("json_type(conversation_starters)='array' AND json_array_length(conversation_starters)<=3"),
        sa.UniqueConstraint('workspace_id','name',name='agent_workspace_name_unique'),
        *checks(['name','avatar_url','description','instructions','model','thinking_level','system_key','service_tier'],
                ['runtime_config','custom_env','custom_args','mcp_config','disabled_runtime_skills','conversation_starters'],
                [('composio_toolkit_allowlist','text')]))
    op.create_index('agent_system_identity_unique','agent',
        ['workspace_id','owner_id','runtime_id','system_key'],unique=True,sqlite_where=sa.text('system_key IS NOT NULL'))
    for name,columns in [('idx_agent_runtime_id',['runtime_id']),('idx_agent_workspace',['workspace_id']),
                         ('idx_agent_workspace_id_keyset',['workspace_id','id'])]:
        op.create_index(name,'agent',columns)


def downgrade():
    raise RuntimeError('Agent/runtime downgrade requires explicit data review')
