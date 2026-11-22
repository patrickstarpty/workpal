"""Nullable local cloud waitlist interest; preserve existing user rows."""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = depends_on = None


def upgrade():
    op.add_column('users', sa.Column('cloud_waitlist_email', sa.String(), nullable=True))
    op.add_column('users', sa.Column('cloud_waitlist_reason', sa.String(), nullable=True))


def downgrade():
    op.drop_column('users', 'cloud_waitlist_reason')
    op.drop_column('users', 'cloud_waitlist_email')
