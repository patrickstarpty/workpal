import sqlite3
import pytest
from fastapi import HTTPException
from workpal_backend.auth.rate_limit import consume
from workpal_backend.infrastructure.database import Database, migrate
from sqlalchemy import text

def test_limit_reset_isolation(settings):
    migrate(settings)
    db = Database(settings)
    for _ in range(5): consume(db, 'send:ip:a', 5, 60, now=100)
    with pytest.raises(HTTPException) as error: consume(db, 'send:ip:a', 5, 60, now=101)
    assert error.value.status_code == 429
    assert error.value.headers['Retry-After'] == '59'
    consume(db, 'send:ip:b', 5, 60, now=101)
    consume(db, 'send:ip:a', 5, 60, now=160)


def test_main_database_only(settings, tmp_path):
    migrate(settings)
    db = Database(settings)
    consume(db, 'a', 1, 60, now=100)
    with db.transaction() as session:
        assert session.execute(text('SELECT count(*) FROM auth_limits')).scalar() == 1
    assert not list(tmp_path.glob('*.auth-limits.sqlite'))
    db.close()


def test_missing_schema_fails_without_writes(settings, tmp_path):
    migrate(settings)
    db = Database(settings)
    with db.transaction() as session:
        session.execute(text('DROP TABLE auth_limits'))
    with pytest.raises(HTTPException) as error:
        consume(db, 'a', 1, 60)
    assert error.value.status_code == 503
    with db.transaction() as session:
        assert session.execute(text("SELECT count(*) FROM sqlite_master WHERE name='auth_limits'")).scalar() == 0
    assert not list(tmp_path.glob('*.auth-limits.sqlite'))
    db.close()


def test_concurrent_and_restart(settings):
    from concurrent.futures import ThreadPoolExecutor
    migrate(settings)
    db = Database(settings)
    def attempt(_):
        try:
            consume(db, 'shared', 5, 60, now=100)
            return 200
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(24)))
    assert outcomes.count(200) == 5
    assert set(outcomes) <= {200, 429}
    db.close()
    db = Database(settings)
    with pytest.raises(HTTPException) as error:
        consume(db, 'shared', 5, 60, now=101)
    assert error.value.status_code == 429
    consume(db, 'shared', 5, 60, now=160)
    consume(db, 'other', 5, 60, now=220)
    with db.transaction() as session:
        assert session.execute(text('SELECT count(*) FROM auth_limits')).scalar() == 1
    db.close()


def test_busy(settings):
    migrate(settings)
    db = Database(settings)
    with db.transaction() as session:
        session.execute(text("INSERT INTO auth_limits VALUES ('locked', 100, 1)"))
        with pytest.raises(HTTPException) as error:
            consume(db, 'a', 1, 60)
        assert error.value.status_code == 503
        assert error.value.headers['Retry-After'] == '1'
    db.close()
