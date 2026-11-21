"""Independent realtime checkpoint, receipts and recoverable quarantine."""
from alembic import op
revision = '0010'
down_revision = '0009'
branch_labels = depends_on = None

def upgrade():
    op.execute('CREATE TABLE realtime_consumer_checkpoint (consumer TEXT PRIMARY KEY NOT NULL, stream_id TEXT NOT NULL)')
    op.execute('CREATE TABLE realtime_consumer_receipt (consumer TEXT NOT NULL, event_id TEXT NOT NULL, PRIMARY KEY (consumer, event_id))')
    op.execute('CREATE TABLE realtime_consumer_quarantine (consumer TEXT NOT NULL, stream_id TEXT NOT NULL, reason TEXT NOT NULL, PRIMARY KEY (consumer, stream_id))')

def downgrade():
    op.drop_table('realtime_consumer_quarantine')
    op.drop_table('realtime_consumer_receipt')
    op.drop_table('realtime_consumer_checkpoint')
