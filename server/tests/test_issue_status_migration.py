"""Exercise historical Alembic DDL against disposable, FK-enabled SQLite files."""
import pytest
from alembic import command
from sqlalchemy import event, create_engine, inspect
from sqlalchemy.exc import IntegrityError
from workpal_backend.infrastructure.database import migration_config


def upgrade(engine, revision):
    with engine.connect() as conn:
        cfg = migration_config()
        cfg.attributes['connection'] = conn
        command.upgrade(cfg, revision)
        conn.commit()


@pytest.fixture
def legacy(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path}/migration.sqlite')
    @event.listens_for(engine, 'connect')
    def foreign_keys(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
    upgrade(engine, '0011')
    with engine.begin() as c:
        c.exec_driver_sql("INSERT INTO users(id,email,name,created_at,updated_at) VALUES ('u','u@example.com','Original','c','u')")
        c.exec_driver_sql("INSERT INTO workspaces(id,name,slug,issue_prefix,created_at,updated_at) VALUES ('w','Workspace','workspace','WP','c','u')")
        c.exec_driver_sql("INSERT INTO members(id,workspace_id,user_id,role,created_at) VALUES ('m','w','u','owner','c')")
        c.exec_driver_sql("INSERT INTO workspace_invitation VALUES ('i','w','u','guest@example.com',NULL,'member','pending','c','u','future')")
        c.exec_driver_sql("INSERT INTO auth_limits VALUES ('neighbor',123.5,7)")
        for key, category in [('backlog','unstarted'),('todo','unstarted'),('in_progress','started'),('in_review','started'),('blocked','started'),('done','done'),('cancelled','closed'),('custom','started')]:
            c.exec_driver_sql('INSERT INTO issue_status VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (key,'w',key,key,'Original description',category,'#abcdef',int(key != 'custom'),2.375,'created','updated',None))
    yield engine
    engine.dispose()


def snapshot(engine):
    with engine.connect() as c:
        return {name: c.exec_driver_sql(f'SELECT * FROM "{name}" ORDER BY 1').fetchall() for name in inspect(c).get_table_names()}


def schema(engine):
    with engine.connect() as c:
        return c.exec_driver_sql("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()


def test_historical_upgrade_preserves_values_and_neighbors(legacy):
    before = snapshot(legacy)
    with legacy.connect() as c:
        assert 'icon' not in {x['name'] for x in inspect(c).get_columns('issue_status')}
        assert 'idx_issue_status_workspace_name_active' not in {x['name'] for x in inspect(c).get_indexes('issue_status')}
    upgrade(legacy, 'head')
    after = snapshot(legacy)
    for table, rows in before.items():
        if table == 'alembic_version':
            continue
        assert after[table] == ([tuple(r) + ('',) for r in rows] if table == 'issue_status' else rows)
    with legacy.connect() as c:
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
        assert c.exec_driver_sql('PRAGMA foreign_key_check').fetchall() == []
        assert str(next(x for x in inspect(c).get_columns('issue_status') if x['name'] == 'position')['type']) == 'FLOAT'
        with pytest.raises(IntegrityError):
            c.exec_driver_sql("DELETE FROM workspaces WHERE id='w'")
    upgrade(legacy, 'head')
    assert snapshot(legacy) == after


@pytest.mark.parametrize('assignment', ["key='Bad Key'", "name=''", "description='" + 'x'*257 + "'", "color='#ABCDEF'", "key='unknown',is_system=1", "is_system=1,archived_at='archived'", "name='TODO'"])
def test_invalid_legacy_upgrade_is_atomic(legacy, assignment):
    with legacy.begin() as c:
        c.exec_driver_sql(f"UPDATE issue_status SET {assignment} WHERE id='custom'")
    before, ddl = snapshot(legacy), schema(legacy)
    with pytest.raises(IntegrityError):
        upgrade(legacy, 'head')
    assert snapshot(legacy) == before
    assert schema(legacy) == ddl
    with legacy.connect() as c:
        assert c.exec_driver_sql('SELECT version_num FROM alembic_version').scalar() == '0011'
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
        assert c.exec_driver_sql('PRAGMA foreign_key_check').fetchall() == []
        assert not any('_alembic_tmp' in n for n in inspect(c).get_table_names())
