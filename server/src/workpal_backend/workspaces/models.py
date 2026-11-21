from sqlalchemy import *
from workpal_backend.auth.models import metadata
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
 *[Column(n, String, nullable=False) for n in ('key','name','category','color')],
 Column('description', String, nullable=False, server_default=''),
 Column('icon', String, nullable=False, server_default=''),
 Column('is_system', Boolean, nullable=False, server_default='0'), Column('position', Float, nullable=False, server_default='0'),
 Column('created_at', String, nullable=False), Column('updated_at', String, nullable=False), Column('archived_at', String),
 UniqueConstraint('workspace_id','key'), CheckConstraint('is_system IN (0,1)'),
 CheckConstraint("category IN ('unstarted','started','done','closed')"),
 CheckConstraint("length(key) BETWEEN 1 AND 32 AND key NOT GLOB '*[^a-z0-9_]*' AND substr(key,1,1) GLOB '[a-z0-9]'", name='issue_status_contract_0'),
 CheckConstraint('length(name) BETWEEN 1 AND 64', name='issue_status_contract_1'),
 CheckConstraint('length(description) <= 256', name='issue_status_contract_2'),
 CheckConstraint("length(color) = 7 AND substr(color,1,1) = '#' AND substr(color,2) NOT GLOB '*[^0-9a-f]*'", name='issue_status_contract_3'),
 CheckConstraint("NOT is_system OR ((key = 'backlog' AND category = 'unstarted') OR (key = 'todo' AND category = 'unstarted') OR (key = 'in_progress' AND category = 'started') OR (key = 'in_review' AND category = 'started') OR (key = 'blocked' AND category = 'started') OR (key = 'done' AND category = 'done') OR (key = 'cancelled' AND category = 'closed'))", name='issue_status_contract_4'),
 CheckConstraint('instr(id, char(0)) = 0 AND instr(workspace_id, char(0)) = 0 AND instr(key, char(0)) = 0 AND instr(name, char(0)) = 0 AND instr(category, char(0)) = 0 AND instr(color, char(0)) = 0 AND instr(description, char(0)) = 0 AND instr(icon, char(0)) = 0 AND instr(created_at, char(0)) = 0 AND instr(updated_at, char(0)) = 0 AND instr(archived_at, char(0)) = 0', name='issue_status_no_nul'),
 CheckConstraint('NOT is_system OR archived_at IS NULL', name='issue_status_contract_5'))
Index('idx_issue_status_workspace_name_active', issue_status.c.workspace_id, func.lower(issue_status.c.name), unique=True, sqlite_where=issue_status.c.archived_at.is_(None))
