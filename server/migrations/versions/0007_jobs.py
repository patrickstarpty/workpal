"""Durable recurring schedules."""
from alembic import op
from workpal_backend.infrastructure.jobs import jobs
revision = '0007'
down_revision = '0006'
branch_labels = depends_on = None

def upgrade():
    jobs.create(op.get_bind())

def downgrade():
    jobs.drop(op.get_bind())
