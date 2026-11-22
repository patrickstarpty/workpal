"""Workspace persistence after users."""
from alembic import op
from sqlalchemy import *
metadata = MetaData()
Table('users', metadata, Column('id', String, primary_key=True))
workspaces = Table('workspaces', metadata,
 Column('id', String, primary_key=True), Column('name', String, nullable=False), Column('slug', String, nullable=False, unique=True),
 *[Column(n, String) for n in ('description','context','avatar_url')],
 Column('settings', JSON, nullable=False, server_default=text("'{}'")), Column('repos', JSON, nullable=False, server_default=text("'[]'")),
 Column('issue_prefix', String, nullable=False), Column('issue_counter', Integer, nullable=False, server_default='0'),
 Column('attribution_fail_closed', Boolean, nullable=False, server_default='0'),
 Column('created_at', String, nullable=False), Column('updated_at', String, nullable=False),
 CheckConstraint('json_valid(settings) AND json_valid(repos)'), CheckConstraint('attribution_fail_closed IN (0,1)'))
members = Table('members', metadata,
 Column('id', String, primary_key=True), Column('workspace_id', String, ForeignKey('workspaces.id'), nullable=False),
 Column('user_id', String, ForeignKey('users.id'), nullable=False), Column('role', String, nullable=False),
 Column('created_at', String, nullable=False), Column('pinned_at', String),
 UniqueConstraint('workspace_id','user_id'), CheckConstraint("role IN ('owner','admin','member')"))
issue_status = Table('issue_status', metadata,
 Column('id', String, primary_key=True), Column('workspace_id', String, ForeignKey('workspaces.id'), nullable=False),
 *[Column(n, String, nullable=False) for n in ('key','name','description','category','color')],
 Column('is_system', Boolean, nullable=False), Column('position', Integer, nullable=False),
 Column('created_at', String, nullable=False), Column('updated_at', String, nullable=False), Column('archived_at', String),
 UniqueConstraint('workspace_id','key'), CheckConstraint('is_system IN (0,1)'),
 CheckConstraint("category IN ('unstarted','started','done','closed')"))

revision = '0003'
down_revision = '0002'
branch_labels = depends_on = None

def upgrade():
    for table in (workspaces, members, issue_status):
        table.create(op.get_bind())

def downgrade():
    for table in (issue_status, members, workspaces):
        table.drop(op.get_bind())
