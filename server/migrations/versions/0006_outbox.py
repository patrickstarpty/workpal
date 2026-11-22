"""Durable transactional event outbox."""
from alembic import op
from workpal_backend.infrastructure.outbox import outbox
revision = '0006'
down_revision = '0005'
branch_labels = depends_on = None

def upgrade():
    outbox.create(op.get_bind())

def downgrade():
    outbox.drop(op.get_bind())
