import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from test_onboarding_json_edges import authenticated


def test_waitlist_storage_and_privacy(authenticated):
    from workpal_backend.auth.waitlist import join_waitlist
    from workpal_backend.auth.models import users
    client, headers = authenticated
    q = {'cloud_waitlist_email': 'questionnaire', 'nested': {'cloud_waitlist_reason': 'keep'}}
    client.patch('/api/me/onboarding', json={'questionnaire': q}, headers=headers)
    db = client.app.state.database
    uid = client.get('/api/me', headers=headers).json()['id']
    with db.transaction() as s:
        before = dict(s.execute(select(users)).mappings().one())
        join_waitlist(s, uid, 'first@example.com', 'interest')
        row = join_waitlist(s, uid, 'second@example.com', None)
        assert row['cloud_waitlist_email'] == 'second@example.com'
        assert row['cloud_waitlist_reason'] is None
        for key in before.keys() - {'updated_at', 'cloud_waitlist_email', 'cloud_waitlist_reason'}:
            assert row[key] == before[key]
    for response in [client.get('/api/me', headers=headers), client.patch('/api/me', json={}, headers=headers), client.patch('/api/me/onboarding', json={}, headers=headers)]:
        assert response.status_code == 200
        assert 'cloud_waitlist_email' not in response.json()
        assert 'cloud_waitlist_reason' not in response.json()
        assert response.json()['onboarding_questionnaire'] == q
    login = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'})
    assert len(login.headers.get_list('set-cookie')) == 3
    assert 'cloud_waitlist_email' not in login.json()['user']
    assert login.json()['user']['onboarding_questionnaire'] == q
    with pytest.raises(RuntimeError):
        with db.transaction() as s:
            join_waitlist(s, uid, 'rollback@example.com', 'rollback')
            raise RuntimeError()
    with db.transaction() as s:
        assert s.execute(select(users.c.cloud_waitlist_email)).scalar_one() == 'second@example.com'
        with pytest.raises(HTTPException) as err:
            join_waitlist(s, 'missing', 'x@example.com', None)
        assert (err.value.status_code, err.value.detail) == (500, 'failed to join waitlist')
        assert s.execute(select(users.c.cloud_waitlist_email)).scalar_one() == 'second@example.com'


def test_upgrade_existing_exact_questionnaire_twice(settings):
    from alembic import command
    from sqlalchemy import create_engine
    from workpal_backend.infrastructure.database import migration_config, migrate, Database
    engine = create_engine(settings.database_url)
    raw = b'{"n":0.12345678901234567890123456789,"cloud_waitlist_email":"keep"}'
    with engine.connect() as conn:
        cfg = migration_config()
        cfg.attributes['connection'] = conn
        command.upgrade(cfg, '0010')
        conn.execute(text("INSERT INTO users (id,email,name,created_at,updated_at,onboarding_questionnaire) VALUES ('old','old@example.com','Old','before','before',:q)"), {'q': raw})
        conn.commit()
    engine.dispose()
    migrate(settings)
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        row = s.execute(text('SELECT * FROM users')).mappings().one()
        assert row['onboarding_questionnaire'] == raw
        assert row['updated_at'] == 'before'
        assert row['cloud_waitlist_email'] is None
        assert row['cloud_waitlist_reason'] is None
    db.close()


def test_caught_database_failure_keeps_outer_transaction(authenticated):
    from workpal_backend.auth.waitlist import join_waitlist
    client, headers = authenticated
    uid = client.get('/api/me', headers=headers).json()['id']
    with client.app.state.database.transaction() as s:
        s.execute(text("CREATE TEMP TRIGGER reject_waitlist BEFORE UPDATE OF cloud_waitlist_email ON users BEGIN SELECT RAISE(ABORT, 'rejected'); END"))
        with pytest.raises(HTTPException) as err:
            join_waitlist(s, uid, 'x@example.com', None)
        assert err.value.detail == 'failed to join waitlist'
        s.execute(text("UPDATE users SET name='outer survives'"))
        assert s.execute(text('SELECT cloud_waitlist_email FROM users')).scalar_one() is None
    assert client.get('/api/me', headers=headers).json()['name'] == 'outer survives'


def test_waitlist_contention_remains_retryable(authenticated):
    import sqlite3
    from workpal_backend.auth.waitlist import join_waitlist
    from workpal_backend.infrastructure.database import DatabaseBusy
    client, headers = authenticated
    uid = client.get('/api/me', headers=headers).json()['id']
    db = client.app.state.database
    with sqlite3.connect(db.settings.database_url.removeprefix('sqlite:///')) as blocker:
        blocker.execute('BEGIN IMMEDIATE')
        try:
            with pytest.raises(DatabaseBusy):
                with db.transaction() as session:
                    join_waitlist(session, uid, 'blocked@example.com', None)
        finally:
            blocker.rollback()
    with db.transaction() as session:
        assert session.execute(text('SELECT cloud_waitlist_email FROM users')).scalar_one() is None
