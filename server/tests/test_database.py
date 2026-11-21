import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from workpal_backend.infrastructure.database import Database, migrate, DatabaseBusy

def test_transactions(settings):
    migrate(settings); migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        s.execute(text('CREATE TABLE parent(id INTEGER PRIMARY KEY)'))
        s.execute(text('CREATE TABLE child(id INTEGER REFERENCES parent(id))'))
    with pytest.raises(IntegrityError):
        with db.transaction() as s: s.execute(text('INSERT INTO child VALUES(1)'))
    with pytest.raises(RuntimeError):
        with db.transaction() as s:
            s.execute(text('INSERT INTO parent VALUES(1)'))
            raise RuntimeError()
    with db.transaction() as s:
        assert s.execute(text('SELECT count(*) FROM parent')).scalar() == 0
        s.execute(text('INSERT INTO parent VALUES(2)'))
    db.close(); db = Database(settings)
    with db.transaction() as s: assert s.execute(text('SELECT id FROM parent')).scalar() == 2
    db.close()

def test_lock_timeout(settings):
    migrate(settings); db = Database(settings)
    with db.transaction() as s:
        s.execute(text('CREATE TABLE locks(id INTEGER)'))
    with db.transaction() as s:
        s.execute(text('INSERT INTO locks VALUES(1)'))
        with pytest.raises(DatabaseBusy):
            with db.transaction() as other: other.execute(text('INSERT INTO locks VALUES(2)'))
    db.close()

@pytest.mark.parametrize('operation', ['migrate', 'health'])
def test_unknown_is_untouched(settings, operation):
    import sqlite3
    from pathlib import Path
    from fastapi.testclient import TestClient
    from workpal_backend.app import create_app
    path = Path(settings.database_url.removeprefix('sqlite:///'))
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE user_data(value TEXT)')
    before = path.read_bytes()
    if operation == 'migrate':
        with pytest.raises(ValueError): migrate(settings)
    else:
        with TestClient(create_app(settings)) as client:
            assert client.get('/readyz').status_code == 503
    assert path.read_bytes() == before
    with sqlite3.connect(path) as conn:
        assert conn.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'

@pytest.mark.parametrize('revision,expected', [(None,'error'),('old','out_of_date'),('current','ok'),('future','out_of_date')])
def test_readiness_versions(settings, revision, expected):
    import sqlite3
    migrate(settings)
    with sqlite3.connect(settings.database_url.removeprefix('sqlite:///')) as conn:
        if revision == 'current':
            revision = conn.execute('SELECT version_num FROM alembic_version').fetchone()[0]
        conn.execute('DELETE FROM alembic_version')
        if revision: conn.execute('INSERT INTO alembic_version VALUES (?)',(revision,))
    db = Database(settings)
    try: assert db.readiness() == expected
    finally: db.close()

def test_readiness_tracks_later_heads(settings, tmp_path, monkeypatch):
    from workpal_backend.infrastructure import database
    from alembic.config import Config
    import sqlite3
    migrate(settings)
    versions = tmp_path/'migrations'/'versions'
    versions.mkdir(parents=True)
    (versions/'first.py').write_text("revision = '0001'\ndown_revision = None\n")
    (versions/'next.py').write_text("revision = '0002'\ndown_revision = '0001'\n")
    cfg = Config()
    cfg.set_main_option('script_location',str(versions.parent))
    monkeypatch.setattr(database,'migration_config',lambda: cfg)
    with sqlite3.connect(settings.database_url.removeprefix('sqlite:///')) as conn:
        conn.execute("UPDATE alembic_version SET version_num='0001'")
    db = Database(settings)
    try:
        assert db.readiness() == 'out_of_date'
        with sqlite3.connect(settings.database_url.removeprefix('sqlite:///')) as conn:
            conn.execute("UPDATE alembic_version SET version_num='0002'")
        assert db.readiness() == 'ok'
    finally: db.close()
