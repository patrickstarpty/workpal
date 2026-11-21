"""Durable upload recovery ledger."""
from alembic import op
from workpal_backend.files.models import upload_intent
revision = '0005'
down_revision = '0004'
branch_labels = depends_on = None

def upgrade():
    upload_intent.create(op.get_bind())

def downgrade():
    upload_intent.drop(op.get_bind())
