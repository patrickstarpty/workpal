import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from workpal_backend.auth.models import users
from workpal_backend.auth.service import get_or_create_development_user, get_user
from workpal_backend.infrastructure.database import Database, migrate


def test_users(settings):
    migrate(settings)
    migrate(settings)
    db = Database(settings)
    try:
        with db.transaction() as session:
            user = get_or_create_development_user(session, ' DEV@Workpal.Local ')
            assert get_or_create_development_user(session, 'dev@workpal.local') == user
            assert get_user(session, user['id']) == user
            assert get_user(session, 'missing') is None
            assert user['email'] == 'dev@workpal.local'
            assert user['onboarding_questionnaire'] == {}
            assert user['profile_description'] == ''
            assert user['star_prompt_shown_count'] == 0
            for field in ('avatar_url', 'language', 'timezone', 'onboarded_at', 'whats_new_seen_version', 'star_prompt_last_shown_at', 'star_prompt_starred_at'):
                assert user[field] is None
            json.dumps(user)
        with pytest.raises(IntegrityError):
            with db.transaction() as session:
                session.execute(users.insert().values(**{**user, 'id': 'duplicate'}))
        db.close()
        db = Database(settings)
        with db.transaction() as session:
            assert get_user(session, user['id']) == user
    finally:
        db.close()


def test_rollback_and_rejection(settings):
    migrate(settings)
    db = Database(settings)
    try:
        with pytest.raises(RuntimeError):
            with db.transaction() as session:
                get_or_create_development_user(session, 'dev@workpal.local')
                raise RuntimeError('rollback')
        with db.transaction() as session:
            for email in ('other@example.com', '', 'dev@workpal.local.evil'):
                with pytest.raises(ValueError):
                    get_or_create_development_user(session, email)
            assert session.scalar(select(func.count()).select_from(users)) == 0
    finally:
        db.close()


def test_concurrent_creation(settings):
    migrate(settings)
    db = Database(settings)
    def create(_):
        with db.transaction() as session:
            return get_or_create_development_user(session, 'dev@workpal.local')['id']
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert len(set(pool.map(create, range(4)))) == 1
        with db.transaction() as session:
            assert session.scalar(select(func.count()).select_from(users)) == 1
    finally:
        db.close()
