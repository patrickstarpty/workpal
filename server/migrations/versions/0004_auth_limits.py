"""Version durable authentication counters with the main database."""
from alembic import op
import sqlalchemy as sa
revision = '0004'
down_revision = '0003'
branch_labels = depends_on = None


def upgrade():
    op.create_table('auth_limits', sa.Column('key', sa.Text(), primary_key=True),
                    sa.Column('expires', sa.Float(), nullable=False),
                    sa.Column('count', sa.Integer(), nullable=False))
    op.create_index('ix_auth_limits_expires', 'auth_limits', ['expires'])


def downgrade():
    op.drop_table('auth_limits')
