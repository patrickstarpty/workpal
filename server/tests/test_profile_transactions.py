"""Real SQLite failures and caller-owned profile transaction boundaries."""
from contextlib import contextmanager
from datetime import datetime
import sqlite3
import time

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from workpal_backend.auth.profile import update_profile
from workpal_backend.auth.profile_routes import persist
from workpal_backend.auth.service import get_or_create_development_user, get_user
from workpal_backend.infrastructure.database import Database, DatabaseBusy, migrate


@pytest.fixture
def profile_db(settings):
    settings.busy_timeout_ms = 80
    migrate(settings)
    db = Database(settings)
    with db.transaction() as session:
        original = get_or_create_development_user(session, 'dev@workpal.local')
    yield db, original
    db.close()


@contextmanager
def sql_failure(db, phase, after=False):
    def fail(conn, cursor, statement, parameters, context, executemany):
        sql = statement.lstrip().upper()
        if (phase == 'load' and sql.startswith('SELECT') and 'FROM USERS' in sql) or (phase == 'update' and sql.startswith('UPDATE USERS')):
            if after:
                raise RuntimeError('post-write failure')
            # Execute invalid SQL on the real DBAPI cursor, wrapped by SQLAlchemy.
            cursor.execute('SELECT * FROM missing_profile_failure_table')
    hook = 'after_cursor_execute' if after else 'before_cursor_execute'
    event.listen(db.engine, hook, fail)
    try:
        yield
    finally:
        event.remove(db.engine, hook, fail)


def assert_unchanged(db, original):
    with db.transaction() as session:
        assert get_user(session, original['id']) == original
        assert session.execute(text('SELECT count(*) FROM outbox')).scalar_one() == 0


@pytest.mark.parametrize('phase,status,detail', [('load', 404, 'user not found'), ('update', 500, 'failed to update user')])
def test_real_sql_failure_route_classification_after_rollback(profile_db, phase, status, detail):
    from fastapi import HTTPException
    db, original = profile_db
    with sql_failure(db, phase), pytest.raises(HTTPException) as error:
        persist(db, original['id'], {'name': 'Changed'})
    assert (error.value.status_code, error.value.detail) == (status, detail)
    assert_unchanged(db, original)


def test_post_write_failure_can_be_caught_before_unrelated_commit(profile_db):
    db, original = profile_db
    with db.transaction() as session:
        with sql_failure(db, 'update', after=True), pytest.raises(RuntimeError, match='post-write failure'):
            update_profile(session, original['id'], {'name': 'Changed'}, ['load'])
        session.execute(text('CREATE TABLE unrelated_profile_write (value TEXT)'))
        session.execute(text("INSERT INTO unrelated_profile_write VALUES ('kept')"))
    assert_unchanged(db, original)
    with db.transaction() as session:
        assert session.execute(text('SELECT value FROM unrelated_profile_write')).scalar_one() == 'kept'


def test_post_write_exception_rolls_back_outer_transaction(profile_db):
    db, original = profile_db
    with sql_failure(db, 'update', after=True), pytest.raises(RuntimeError, match='post-write failure'):
        persist(db, original['id'], {'name': 'Changed'})
    assert_unchanged(db, original)


def test_success_return_values_and_caller_rollback(profile_db):
    db, original = profile_db
    with pytest.raises(RuntimeError, match='caller abort'):
        with db.transaction() as session:
            returned = update_profile(session, original['id'], {'name': ' Changed '}, ['load'])
            assert returned['name'] == 'Changed'
            assert returned['updated_at'] != original['updated_at']
            assert datetime.fromisoformat(returned['updated_at'].replace('Z', '+00:00')).tzinfo is not None
            assert get_user(session, original['id']) == returned
            raise RuntimeError('caller abort')
    assert_unchanged(db, original)
    returned = persist(db, original['id'], {})
    assert returned['name'] == original['name']
    assert returned['created_at'] == original['created_at']
    assert returned['updated_at'] != original['updated_at']
    with db.transaction() as session:
        assert get_user(session, original['id']) == returned
        assert session.execute(text('SELECT count(*) FROM outbox')).scalar_one() == 0


def test_actual_sqlite_lock_returns_503_with_bounded_wait(profile_db):
    db, original = profile_db
    app = FastAPI()
    @app.exception_handler(DatabaseBusy)
    async def busy(request, exc):
        return JSONResponse({'error': str(exc)}, status_code=503)
    @app.patch('/profile')
    def patch():
        return persist(db, original['id'], {'name': 'Changed'})
    path = db.settings.database_url.removeprefix('sqlite:///')
    with sqlite3.connect(path) as blocker, TestClient(app) as client:
        blocker.execute('BEGIN IMMEDIATE')
        started = time.monotonic()
        response = client.patch('/profile')
        elapsed = time.monotonic() - started
        blocker.rollback()
    assert response.status_code == 503
    assert response.json() == {'error': 'Database is busy; retry later'}
    assert 0.04 <= elapsed < 2
    assert_unchanged(db, original)
