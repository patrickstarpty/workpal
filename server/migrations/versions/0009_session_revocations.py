"""Durable session revocation without storing credentials."""
from alembic import op
from workpal_backend.auth.sessions import revocations
revision = '0009'
down_revision = '0008'
branch_labels = depends_on = None

def upgrade():
    revocations.create(op.get_bind())

def downgrade():
    revocations.drop(op.get_bind())
