"""Workspace content retained from the local legacy store."""
from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, JSON, String, Table, Text

from workpal_backend.workspaces.models import metadata

records = Table(
    'workspace_records', metadata,
    Column('workspace_id', String, ForeignKey('workspaces.id'), primary_key=True),
    Column('kind', Text, primary_key=True),
    Column('id', Text, primary_key=True),
    Column('body', JSON, nullable=False),
    Column('source_body', Text),
    Column('position', Integer, nullable=False, server_default='0'),
    CheckConstraint("json_valid(body) AND json_type(body) = 'object'", name='workspace_records_body_object'),
    CheckConstraint('source_body IS NULL OR json_valid(source_body)', name='workspace_records_source_json'),
)
Index('idx_workspace_records_order', records.c.workspace_id, records.c.kind, records.c.position)

legacy_imports = Table(
    'legacy_imports', metadata,
    Column('source_id', String, primary_key=True),
    Column('source_path', Text, nullable=False),
    Column('source_checksum', String, nullable=False),
    Column('workspace_id', String, ForeignKey('workspaces.id'), nullable=False, unique=True),
    Column('owner_id', String, ForeignKey('users.id'), nullable=False),
    Column('mapping', JSON, nullable=False),
    Column('counts', JSON, nullable=False),
    Column('created_at', String, nullable=False),
    CheckConstraint('json_valid(mapping) AND json_valid(counts)', name='legacy_imports_json'),
)
