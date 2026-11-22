"""Durable ownership snapshots deliberately have no cascading foreign keys."""
from sqlalchemy import Table, Column, String, Float, Integer, JSON, MetaData, CheckConstraint, Index
metadata = MetaData()
upload_intent = Table('upload_intent', metadata,
    Column('id', String, primary_key=True),
    Column('attachment_id', String, unique=True),
    Column('storage_key', String, nullable=False, unique=True),
    Column('staging_key', String, nullable=False, unique=True),
    Column('owner_type', String, nullable=False), Column('owner_id', String, nullable=False),
    Column('workspace_id', String), Column('target_json', JSON, nullable=False),
    Column('state', String, nullable=False), Column('lease_token', String, nullable=False),
    Column('lease_expires_at', Float, nullable=False),
    Column('size_bytes', Integer), Column('sha256', String), Column('content_type', String),
    Column('filename', String), Column('width', Integer), Column('height', Integer),
    Column('next_attempt_at', Float, nullable=False), Column('last_error', String),
    Column('created_at', Float, nullable=False), Column('updated_at', Float, nullable=False),
    CheckConstraint("state IN ('pending','ready','failed','deleting')"),
    CheckConstraint('size_bytes IS NULL OR size_bytes >= 0'))
Index('ix_upload_cleanup', upload_intent.c.state, upload_intent.c.lease_expires_at, upload_intent.c.next_attempt_at)
