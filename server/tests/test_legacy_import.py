"""Legacy import retains history and identity without overwriting later edits."""
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select, update

from workpal_backend.auth.models import users
from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.workspaces.models import issue_status, members, workspaces

OWNER_ID = 'dc9a03bb-3c13-40fe-aac9-83a77492ff77'
STAMP = '2026-11-20T00:00:00Z'


@pytest.fixture
def target(settings):
    migrate(settings)
    db = Database(settings)
    with db.engine.begin() as conn:
        conn.execute(users.insert().values(id=OWNER_ID, email='dev@workpal.local', name='Developer', created_at=STAMP, updated_at=STAMP))
    yield db
    db.close()


@pytest.fixture
def source(tmp_path):
    path = tmp_path/'legacy.sqlite'
    rows = [
        ('workspaces', 'review-workspace', {'id':'review-workspace','slug':'review','name':'TAP','role':'owner','created_at':STAMP}),
        ('users', 'patrick', {'id':'patrick','name':'Patrick','email':'review@example.invalid','created_at':STAMP,'onboarding_questionnaire':{'source_skipped':True}}),
        ('projects', 'TAP', {'id':'TAP','workspace_id':'review-workspace','creator_type':'member','creator_id':'patrick','lead_type':'member','lead_id':'patrick'}),
        ('issues', 'TAP-1', {'id':'TAP-1','workspace_id':'review-workspace','number':28,'project_id':'TAP','creator_type':'member','creator_id':'patrick','assignee_type':'member','assignee_id':'patrick','description':'patrick','metadata':{'note':'review-workspace'},'labels':[{'id':'label','workspace_id':'review-workspace'}]}),
        ('comments', 'comment-1', {'id':'comment-1','issue_id':'TAP-1','author_type':'member','author_id':'patrick','content':'review-workspace'}),
        ('squads', 'squad', {'id':'squad','workspace_id':'review-workspace','member_preview':[{'member_type':'member','member_id':'patrick'},{'member_type':'agent','member_id':'patrick'}]}),
        ('sessions', 'chat', {'id':'chat','workspace_id':'review-workspace','creator_id':'patrick','messages':[{'id':'message','role':'user','text':'patrick'}]}),
        ('skills', 'skill', {'id':'skill','workspace_id':'review-workspace','created_by':'patrick','description':'review-workspace'}),
        ('agents', 'agent', {'id':'agent','workspace_id':'review-workspace','owner_id':'patrick','skills':[{'id':'skill','created_by':'patrick'}]}),
        ('runtimes', 'runtime', {'id':'runtime','workspace_id':'review-workspace','owner_id':'patrick'}),
        ('analytics_runs', 'run', {'id':'run','issue_id':'TAP-1','agent_id':'agent','task_count':1}),
        ('contribution_data', 'workspace', {'id':'workspace','commits':[{'message':'patrick','task':'TAP-1'}]}),
    ]
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE records(kind TEXT NOT NULL,id TEXT NOT NULL,body TEXT NOT NULL,PRIMARY KEY(kind,id))')
        conn.execute('CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT)')
        conn.executemany('INSERT INTO records VALUES(?,?,?)', [(kind,id,json.dumps(body, ensure_ascii=False)) for kind,id,body in rows])
    return path


def importer():
    assert importlib.util.find_spec('workpal_backend.legacy_import') is not None, 'Legacy importer is not implemented'
    from workpal_backend.legacy_import import import_legacy
    return import_legacy


def test_import_preserves_every_record_and_canonical_access(target, source):
    result = importer()(target.engine, source, 'dev@workpal.local')
    from workpal_backend.workspace_content.models import records
    wid = result['mapping']['workspaces']['review-workspace']
    uid = result['mapping']['users']['patrick']
    assert str(UUID(wid)) == wid and str(UUID(uid)) == uid
    assert result['total_records'] == 12
    assert result['counts'] == dict.fromkeys(['workspaces','users','projects','issues','comments','squads','sessions','skills','agents','runtimes','analytics_runs','contribution_data'], 1)
    with target.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(records)) == 12
        workspace = conn.execute(select(workspaces)).mappings().one()
        assert (workspace['name'], workspace['slug'], workspace['issue_prefix'], workspace['issue_counter']) == ('TAP','review','TAP',28)
        assert conn.execute(select(users.c.id, users.c.name).where(users.c.email == 'review@example.invalid')).one() == (uid, 'Patrick')
        assert conn.execute(select(users.c.id, users.c.name).where(users.c.email == 'dev@workpal.local')).one() == (OWNER_ID,'Developer')
        assert conn.execute(select(members.c.id,members.c.role).where(members.c.user_id == uid)).one() == (uid,'owner')
        assert conn.execute(select(members.c.workspace_id,members.c.role).where(members.c.user_id == OWNER_ID)).one() == (wid,'owner')
        assert conn.scalar(select(func.count()).select_from(issue_status).where(issue_status.c.workspace_id == wid)) == 7
        imported = conn.execute(select(records).order_by(records.c.position)).mappings().all()
    with sqlite3.connect(source) as conn:
        original = conn.execute('SELECT kind,id,body FROM records ORDER BY rowid').fetchall()
    assert [(r['kind'], r['source_body']) for r in imported] == [(kind, body) for kind,id,body in original]
    assert [r['position'] for r in imported] == list(range(12))
    by_kind = {r['kind']:r['body'] for r in imported}
    assert by_kind['issues']['creator_id'] == uid
    assert by_kind['issues']['assignee_id'] == uid
    assert by_kind['issues']['labels'][0]['workspace_id'] == wid
    assert by_kind['issues']['description'] == 'patrick'
    assert by_kind['issues']['metadata']['note'] == 'review-workspace'
    assert by_kind['comments']['author_id'] == uid
    assert by_kind['comments']['content'] == 'review-workspace'
    assert by_kind['squads']['member_preview'] == [{'member_type':'member','member_id':uid},{'member_type':'agent','member_id':'patrick'}]
    assert by_kind['agents']['skills'][0]['created_by'] == uid
    assert by_kind['sessions']['messages'][0]['text'] == 'patrick'
    assert by_kind['users']['id'] == uid
    assert by_kind['workspaces']['id'] == wid


def test_rerun_preserves_edits_and_rejects_changed_source(target, source):
    run = importer()
    first = run(target.engine, source, 'dev@workpal.local')
    from workpal_backend.workspace_content.models import records
    with target.engine.begin() as conn:
        conn.execute(update(records).where(records.c.kind=='issues').values(body={'id':'TAP-1','title':'Changed after import'}))
        conn.execute(update(workspaces).values(name='Renamed later'))
    again = run(target.engine, source, 'dev@workpal.local')
    assert again['already_imported'] is True
    assert again['mapping'] == first['mapping']
    with target.engine.connect() as conn:
        assert conn.scalar(select(records.c.body).where(records.c.kind=='issues'))['title'] == 'Changed after import'
        assert conn.scalar(select(workspaces.c.name)) == 'Renamed later'
    with sqlite3.connect(source) as conn:
        conn.execute("UPDATE records SET body=json_set(body,'$.title','Source changed') WHERE kind='issues'")
    with pytest.raises(ValueError, match='changed'):
        run(target.engine, source, 'dev@workpal.local')


def test_failure_rolls_back_all_import_rows(target, source):
    run = importer()
    with target.engine.begin() as conn:
        conn.exec_driver_sql("CREATE TRIGGER reject_legacy_issue BEFORE INSERT ON workspace_records WHEN NEW.kind='issues' BEGIN SELECT RAISE(ABORT,'forced record failure'); END")
    with pytest.raises(Exception, match='forced record failure'):
        run(target.engine, source, 'dev@workpal.local')
    with target.engine.connect() as conn:
        for name in ['workspaces','members','issue_status','workspace_records','legacy_imports']:
            assert conn.exec_driver_sql(f'SELECT count(*) FROM {name}').scalar() == 0
        assert conn.scalar(select(func.count()).select_from(users)) == 1


def test_dry_run_leaves_source_and_target_unchanged(target, source):
    run = importer()
    target_path = Path(target.engine.url.database)
    with target.engine.connect() as conn:
        conn.exec_driver_sql('PRAGMA wal_checkpoint(TRUNCATE)')
    before = (source.read_bytes(),target_path.read_bytes())
    result = run(target.engine, source, 'dev@workpal.local', dry_run=True)
    assert result['total_records'] == 12 and result['already_imported'] is False
    assert (source.read_bytes(),target_path.read_bytes()) == before
    with target.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(workspaces)) == 0


@pytest.mark.parametrize('problem', ['missing_owner','source_target_alias','body_id','schema','foreign_workspace','slug_conflict'])
def test_rejects_invalid_source_or_target_without_import(target, source, tmp_path, problem):
    run = importer()
    owner = 'dev@workpal.local'
    if problem == 'missing_owner': owner = 'missing@example.invalid'
    elif problem == 'source_target_alias':
        source = tmp_path/'alias.sqlite'
        source.hardlink_to(target.engine.url.database)
    elif problem == 'slug_conflict':
        with target.engine.begin() as conn:
            conn.execute(workspaces.insert().values(id='existing',name='Existing',slug='review',issue_prefix='EX',created_at=STAMP,updated_at=STAMP))
    else:
        with sqlite3.connect(source) as conn:
            if problem == 'body_id': conn.execute("UPDATE records SET body=json_set(body,'$.id','wrong') WHERE kind='issues'")
            if problem == 'schema': conn.execute('CREATE TABLE unknown(value TEXT)')
            if problem == 'foreign_workspace': conn.execute("UPDATE records SET body=json_set(body,'$.workspace_id','unknown') WHERE kind='issues'")
    with pytest.raises(ValueError): run(target.engine, source, owner)
    with target.engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT count(*) FROM workspace_records').scalar() == 0
        assert conn.scalar(select(func.count()).select_from(users)) == 1


def test_cli_dry_run_does_not_migrate_then_import_is_repeatable(target, source):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root/'src'), WORKPAL_DATABASE_URL=str(target.engine.url))
    command = [sys.executable, '-m', 'workpal_backend.cli', 'import-legacy', '--source', str(source), '--owner-email', 'dev@workpal.local']
    with target.engine.begin() as conn:
        conn.exec_driver_sql('DROP TABLE activity_log')
        conn.exec_driver_sql('DROP TABLE project')
        conn.exec_driver_sql('DROP TABLE search_index_change')
        conn.exec_driver_sql('DROP TABLE search_index_prune_mark')
        conn.exec_driver_sql('DROP TABLE workpal_transaction_clock')
        conn.exec_driver_sql('DROP TABLE chat_session')
        conn.exec_driver_sql('DROP TABLE agent_skill')
        conn.exec_driver_sql('DROP TABLE skill')
        conn.exec_driver_sql('DROP TABLE agent')
        conn.exec_driver_sql('DROP TABLE agent_runtime')
        conn.exec_driver_sql('DROP TABLE personal_access_tokens')
        conn.exec_driver_sql('DROP TABLE legacy_imports')
        conn.exec_driver_sql('DROP TABLE workspace_records')
        conn.exec_driver_sql("UPDATE alembic_version SET version_num='0013'")
    result = subprocess.run(command + ['--dry-run'], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['migration_required'] is True and report['total_records'] == 12
    with target.engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalar() == '0013'
        assert conn.scalar(select(func.count()).select_from(workspaces)) == 0
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode != 0 and 'migrations' in result.stderr
    migrate(target.settings)
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['already_imported'] is False
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['already_imported'] is True


def test_missing_target_dry_run_does_not_create_a_database(source, tmp_path):
    from sqlalchemy import create_engine
    path = tmp_path/'absent.sqlite'
    engine = create_engine(f'sqlite:///{path}')
    try:
        with pytest.raises(ValueError, match='already exist'):
            importer()(engine, source, 'dev@workpal.local', dry_run=True)
        assert not path.exists()
    finally:
        engine.dispose()


def test_legacy_preferences_are_attributed_to_historical_user(target, source):
    with sqlite3.connect(source) as conn:
        conn.execute('INSERT INTO records VALUES(?,?,?)', ('preferences','/issues?view=all',json.dumps({'id':'/issues?view=all','sort':'priority'})))
    result = importer()(target.engine, source, 'dev@workpal.local')
    from workpal_backend.workspace_content.models import records
    with target.engine.connect() as conn:
        row = conn.execute(select(records).where(records.c.kind == 'preferences')).mappings().one()
    assert row['id'] == '/issues?view=all'
    assert row['body']['user_id'] == result['mapping']['users']['patrick']
    assert 'user_id' not in json.loads(row['source_body'])


def test_duplicate_user_email_is_rejected_during_dry_run(target, source):
    with sqlite3.connect(source) as conn:
        conn.execute('INSERT INTO records VALUES(?,?,?)', ('users','duplicate',json.dumps({'id':'duplicate','name':'Other','email':'review@example.invalid','created_at':STAMP})))
    with pytest.raises(ValueError, match='duplicate'):
        importer()(target.engine, source, 'dev@workpal.local', dry_run=True)


def test_autopilot_creator_keeps_native_member_reference(target, source):
    with sqlite3.connect(source) as conn:
        for kind in ('member', 'agent'):
            body = {'id':kind, 'created_by_type':kind, 'created_by_id':'patrick'}
            conn.execute('INSERT INTO records VALUES(?,?,?)', ('autopilots',kind,json.dumps(body)))
    result = importer()(target.engine, source, 'dev@workpal.local')
    from workpal_backend.workspace_content.models import records
    with target.engine.connect() as conn:
        bodies = dict(conn.execute(select(records.c.id, records.c.body).where(records.c.kind == 'autopilots')).all())
    assert bodies['member']['created_by_id'] == result['mapping']['users']['patrick']
    assert bodies['agent']['created_by_id'] == 'patrick'


def test_audit_blocks_unknown_deletion_despite_unchanged_manifest(target, source):
    from workpal_backend.legacy_audit import audit
    importer()(target.engine, source, 'dev@workpal.local')
    assert audit(source, target.engine.url.database)['ok']
    with target.engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM workspace_records WHERE kind='comments'")
    assert importer()(target.engine, source, 'dev@workpal.local')['total_records'] == 12
    result = audit(source, target.engine.url.database)
    assert not result['ok']
    assert result['missing_unknown_reason'] == [['comments', 'comment-1']]
    assert result['target_count'] == 11

@pytest.mark.parametrize('mutation', ['counts', 'mapping', 'owner', 'member', 'position'])
def test_audit_rejects_structural_corruption(target, source, mutation):
    from workpal_backend.legacy_audit import audit
    importer()(target.engine, source, 'dev@workpal.local')
    with target.engine.begin() as conn:
        sql = {
            'counts': "UPDATE legacy_imports SET counts='{}'",
            'mapping': "UPDATE legacy_imports SET mapping='{}'",
            'owner': "UPDATE legacy_imports SET owner_id='missing'",
            'member': "DELETE FROM members",
            'position': "UPDATE workspace_records SET position=999 WHERE kind='issues'",
        }[mutation]
        conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
        if mutation == 'owner':
            conn.exec_driver_sql("UPDATE legacy_imports SET owner_id=(SELECT id FROM users WHERE email='review@example.invalid')")
            conn.exec_driver_sql("DELETE FROM members WHERE user_id=(SELECT id FROM users WHERE email='review@example.invalid')")
        else:
            conn.exec_driver_sql(sql)
    assert not audit(source, target.engine.url.database)['ok']


@pytest.mark.parametrize('change', ['add', 'edit', 'delete'])
def test_audit_baseline_invalidated_by_later_writes(target, source, change):
    from workpal_backend.legacy_audit import audit
    importer()(target.engine, source, 'dev@workpal.local')
    baseline = audit(source, target.engine.url.database)['source_checksum']
    assert audit(source, target.engine.url.database, expected_checksum=baseline)['ok']
    with sqlite3.connect(source) as conn:
        if change == 'add':
            conn.execute("INSERT INTO records VALUES('comments','new','{\"id\":\"new\"}')")
        elif change == 'edit':
            conn.execute("UPDATE records SET body=json_set(body,'$.title','later') WHERE kind='issues'")
        else:
            conn.execute("DELETE FROM records WHERE kind='comments'")
    report = audit(source, target.engine.url.database, expected_checksum=baseline)
    assert not report['ok'] and report['baseline_changed']
    assert report['preflight_only']

@pytest.mark.parametrize('raw', ['{"id":"TAP-1","secret":"DO_NOT_PRINT","id":"other"}', '{"id":"TAP-1","x":NaN}', '[]', '{broken'])
def test_audit_cli_rejects_bad_json_without_disclosure(target, source, raw):
    importer()(target.engine, source, 'dev@workpal.local')
    with sqlite3.connect(source) as conn:
        conn.execute("UPDATE records SET body=? WHERE kind='issues'", (raw,))
    root = Path(__file__).resolve().parents[1]
    before = source.read_bytes()
    result = subprocess.run([sys.executable, str(root/'tools/audit_legacy_import.py'), '--source', str(source), '--target', str(target.engine.url.database)],
                            env=dict(os.environ, PYTHONPATH=str(root/'src')), capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)['ok'] is False
    assert 'DO_NOT_PRINT' not in result.stdout + result.stderr
    assert source.read_bytes() == before


def test_audit_reports_edits_and_accepts_native_display_changes(target, source):
    from workpal_backend.legacy_audit import audit
    importer()(target.engine, source, 'dev@workpal.local')
    with target.engine.begin() as conn:
        conn.exec_driver_sql("UPDATE workspace_records SET body='{\"id\":\"TAP-1\",\"title\":\"later\"}' WHERE kind='issues'")
        conn.exec_driver_sql("UPDATE workspaces SET name='Later'")
        conn.exec_driver_sql("UPDATE users SET name='Later'")
        conn.exec_driver_sql("UPDATE members SET role='member' WHERE user_id != ?", (OWNER_ID,))
    report = audit(source, target.engine.url.database)
    assert report['ok'] and report['current_body_changes'] == [['issues', 'TAP-1']]
    with target.engine.connect() as conn:
        assert 'later' in conn.exec_driver_sql("SELECT body FROM workspace_records WHERE kind='issues'").scalar()


def test_audit_unknown_schema_fails(target, source):
    from workpal_backend.legacy_audit import audit
    importer()(target.engine, source, 'dev@workpal.local')
    with sqlite3.connect(source) as conn:
        conn.execute('CREATE TABLE unknown(secret TEXT)')
    assert not audit(source, target.engine.url.database)['ok']

@pytest.mark.parametrize('sql', [
    "UPDATE legacy_imports SET mapping='{\"users\":{},\"users\":{}}'",
    "UPDATE legacy_imports SET counts='{\"issues\":NaN}'",
    "UPDATE workspace_records SET body='{\"id\":\"x\",\"id\":\"y\"}' WHERE kind='issues'",
    "UPDATE workspace_records SET source_body='{}' WHERE kind='issues'",
    "DELETE FROM workspace_records WHERE kind='comments'",
])
def test_audit_cli_failure_is_read_only(target, source, sql):
    importer()(target.engine, source, 'dev@workpal.local')
    with target.engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA ignore_check_constraints=ON')
        conn.exec_driver_sql(sql)
        conn.exec_driver_sql('PRAGMA ignore_check_constraints=OFF')
    root = Path(__file__).resolve().parents[1]
    path = Path(target.engine.url.database)
    with sqlite3.connect(path) as conn:
        before = '\n'.join(conn.iterdump())
    result = subprocess.run([sys.executable, str(root/'tools/audit_legacy_import.py'), '--source', str(source), '--target', str(path)],
                            env=dict(os.environ, PYTHONPATH=str(root/'src')), capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)['ok'] is False
    with sqlite3.connect(path) as conn:
        assert '\n'.join(conn.iterdump()) == before
