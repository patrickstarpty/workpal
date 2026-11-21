"""SQLAlchemy Core user response storage, with UTC timestamps serialized as text."""
from sqlalchemy import Column, Integer, MetaData, String, Table, CheckConstraint, text

from .json_codec import QuestionnaireJSON

metadata = MetaData()
users = Table(
    'users', metadata,
    Column('id', String, primary_key=True),
    Column('email', String, nullable=False, unique=True),
    Column('name', String, nullable=False),
    Column('avatar_url', String),
    Column('language', String(20)),
    Column('timezone', String),
    Column('onboarded_at', String),
    Column('cloud_waitlist_email', String),
    Column('cloud_waitlist_reason', String),
    Column('onboarding_questionnaire', QuestionnaireJSON(), nullable=False, server_default=text("'{}'")),
    Column('profile_description', String, nullable=False, server_default=text("''")),
    Column('whats_new_seen_version', String),
    Column('star_prompt_shown_count', Integer, nullable=False, server_default=text('0')),
    Column('star_prompt_last_shown_at', String),
    Column('star_prompt_starred_at', String),
    Column('created_at', String, nullable=False),
    Column('updated_at', String, nullable=False),
    CheckConstraint('json_valid(onboarding_questionnaire)', name='users_questionnaire_json'),
    CheckConstraint('email = lower(trim(email))', name='users_email_normalized'),
)
