"""Personal access tokens, corresponding to Go migration 011."""
from alembic import op
import sqlalchemy as sa
revision = '0015'
down_revision = '0014'
branch_labels = depends_on = None


def upgrade():
    op.create_table('personal_access_tokens',
        sa.Column('id',sa.String(),primary_key=True),
        sa.Column('user_id',sa.String(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('name',sa.Text(),nullable=False),
        sa.Column('token_hash',sa.Text(),nullable=False,unique=True),
        sa.Column('token_prefix',sa.Text(),nullable=False),
        sa.Column('expires_at',sa.Float()), sa.Column('last_used_at',sa.Float()),
        sa.Column('revoked',sa.Boolean(),nullable=False,server_default='0'),
        sa.Column('created_at',sa.Float(),nullable=False),
        sa.CheckConstraint('revoked IN (0,1)'),
        sa.CheckConstraint('instr(name, char(0)) = 0 AND instr(token_hash, char(0)) = 0 AND instr(token_prefix, char(0)) = 0',name='personal_access_tokens_no_nul'))
    op.create_index('idx_personal_access_tokens_user','personal_access_tokens',['user_id','revoked'])


def downgrade():
    raise RuntimeError('Token downgrade requires explicit data review')
