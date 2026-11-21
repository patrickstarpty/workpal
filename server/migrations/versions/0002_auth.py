"""Persist development users and full user response fields."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False, unique=True),
        sa.Column('name', sa.String(), nullable=False),
        *[sa.Column(name, sa.String()) for name in ('avatar_url', 'timezone', 'onboarded_at', 'whats_new_seen_version', 'star_prompt_last_shown_at', 'star_prompt_starred_at')],
        sa.Column('language', sa.String(20)),
        sa.Column('onboarding_questionnaire', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('profile_description', sa.String(), nullable=False, server_default=sa.text("''")),
        sa.Column('star_prompt_shown_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('updated_at', sa.String(), nullable=False),
        sa.CheckConstraint('json_valid(onboarding_questionnaire)', name='users_questionnaire_json'),
        sa.CheckConstraint('email = lower(trim(email))', name='users_email_normalized'),
    )


def downgrade():
    op.drop_table('users')
