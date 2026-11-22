"""Retain imported workspace content and an immutable import manifest."""
from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        'workspace_records',
        sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), primary_key=True),
        sa.Column('kind', sa.Text(), primary_key=True),
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('body', sa.JSON(), nullable=False),
        sa.Column('source_body', sa.Text()),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.CheckConstraint("json_valid(body) AND json_type(body) = 'object'", name='workspace_records_body_object'),
        sa.CheckConstraint('source_body IS NULL OR json_valid(source_body)', name='workspace_records_source_json'),
    )
    op.create_index('idx_workspace_records_order', 'workspace_records', ['workspace_id','kind','position'])
    op.create_table(
        'legacy_imports',
        sa.Column('source_id', sa.String(), primary_key=True),
        sa.Column('source_path', sa.Text(), nullable=False),
        sa.Column('source_checksum', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), nullable=False, unique=True),
        sa.Column('owner_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('mapping', sa.JSON(), nullable=False),
        sa.Column('counts', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.CheckConstraint('json_valid(mapping) AND json_valid(counts)', name='legacy_imports_json'),
    )


def downgrade():
    raise RuntimeError('Workspace content downgrade requires explicit data review')
