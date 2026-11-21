"""Invitation persistence; final source FK audit: migrations 041 through head."""
from alembic import op
revision = '0008'
down_revision = '0007'
branch_labels = depends_on = None

def upgrade():
    op.execute("""CREATE TABLE workspace_invitation (
      id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
      inviter_id TEXT NOT NULL REFERENCES users(id), invitee_email TEXT NOT NULL,
      invitee_user_id TEXT REFERENCES users(id), role TEXT NOT NULL CHECK(role IN ('admin','member')),
      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined','expired')),
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, expires_at TEXT NOT NULL)""")
    op.execute("CREATE UNIQUE INDEX idx_invitation_unique_pending ON workspace_invitation(workspace_id, invitee_email) WHERE status='pending'")
    op.execute("CREATE INDEX idx_invitation_invitee_email ON workspace_invitation(invitee_email) WHERE status='pending'")
    op.execute("CREATE INDEX idx_invitation_invitee_user_id ON workspace_invitation(invitee_user_id) WHERE status='pending'")

def downgrade():
    op.drop_table('workspace_invitation')
