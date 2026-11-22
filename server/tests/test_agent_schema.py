"""Canonical agent/runtime persistence constraints; no agent execution fixtures."""
import time
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.auth.service import get_or_create_development_user
from workpal_backend.workspaces.service import create_workspace


@pytest.fixture
def store(settings):
    migrate(settings)
    db=Database(settings)
    with db.transaction() as session:
        uid=get_or_create_development_user(session,'dev@workpal.local')['id']
        wid=create_workspace(session,uid,'Runtime fixture','runtime-fixture')['id']
    yield db,uid,wid
    db.close()


def runtime(session,wid,**values):
    values=dict(workspace_id=wid,name='Runtime',runtime_mode='local',provider='claude-code') | values
    keys=','.join(values)
    params=','.join(':'+k for k in values)
    return session.execute(text(f'INSERT INTO agent_runtime ({keys}) VALUES ({params}) RETURNING *'),values).mappings().one()


def agent(session,wid,**values):
    values=dict(workspace_id=wid,name='Agent',runtime_mode='local') | values
    keys=','.join(values)
    params=','.join(':'+k for k in values)
    return session.execute(text(f'INSERT INTO agent ({keys}) VALUES ({params}) RETURNING *'),values).mappings().one()


def test_defaults_and_transaction_stable_timestamps(store):
    db,uid,wid=store
    with db.transaction() as session:
        r=runtime(session,wid,owner_id=uid)
        a=agent(session,wid,owner_id=uid,runtime_id=r['id'])
        assert r['status']=='offline' and r['visibility']=='private'
        assert r['shared_with']=='[]'
        assert a['max_concurrent_tasks']==6 and a['permission_mode']=='private'
        assert a['kind']=='user' and a['conversation_starters']=='[]'
        assert a['runtime_config']=='{}' and a['disabled_runtime_skills']=='[]'
        assert a['created_at']==a['updated_at']==r['created_at']==r['updated_at']
        assert a['id']!=r['id']
    with db.transaction() as session:
        assert session.scalar(text('SELECT count(*) FROM agent'))==1


@pytest.mark.parametrize('table,field,value',[
    ('agent','runtime_mode','bad'),('agent','status','online'),
    ('agent','visibility','public'),('agent','permission_mode','workspace'),
    ('agent','kind','fake'),('agent','description','x'*256),
    ('agent','conversation_starters','{}'),('agent','conversation_starters','[1,2,3,4]'),
    ('agent','custom_env','not-json'),('agent','name','bad\0name'),
    ('agent_runtime','status','working'),('agent_runtime','visibility','workspace'),
    ('agent_runtime','shared_with','{}'),
])
def test_persisted_constraints(store,table,field,value):
    db,uid,wid=store
    with pytest.raises(IntegrityError):
        with db.transaction() as session:
            row=(agent if table=='agent' else runtime)(session,wid)
            session.execute(text(f'UPDATE {table} SET {field}=:value WHERE id=:id'),dict(value=value,id=row['id']))


def test_runtime_profile_uniqueness_and_agent_reference_restriction(store):
    db,uid,wid=store
    with db.transaction() as session:
        r=runtime(session,wid,daemon_id='daemon')
        a=agent(session,wid,runtime_id=r['id'])
    with pytest.raises(IntegrityError):
        with db.transaction() as session:runtime(session,wid,daemon_id='daemon')
    with db.transaction() as session:
        profile=str(uuid4())
        runtime(session,wid,daemon_id='daemon',profile_id=profile)
    with pytest.raises(IntegrityError):
        with db.transaction() as session:runtime(session,wid,daemon_id='daemon',profile_id=profile)
    with pytest.raises(IntegrityError):
        with db.transaction() as session:session.execute(text('DELETE FROM agent_runtime WHERE id=:id'),dict(id=r['id']))
    with db.transaction() as session:
        session.execute(text('DELETE FROM agent WHERE id=:id'),dict(id=a['id']))
        session.execute(text('DELETE FROM agent_runtime WHERE id=:id'),dict(id=r['id']))


def test_catalog_columns_match_frozen_migrated_go_schema(store):
    import json
    from pathlib import Path
    db,_,_=store
    catalog=json.loads((Path(__file__).parents[2]/'docs/superpowers/evidence/2026-11-22-go-reference-schema.json').read_text())
    with db.transaction() as session:
        for table in ['agent','agent_runtime']:
            actual=session.execute(text('PRAGMA table_info('+table+')')).mappings().all()
            expected=[c for c in catalog['columns'] if c['table_name']==table]
            assert [c['name'] for c in actual]==[c['column_name'] for c in expected]
            assert {c['name']:bool(c['notnull'] or c['pk']) for c in actual}=={
                c['column_name']:c['is_nullable']=='NO' for c in expected}


@pytest.mark.parametrize('table',['agent','agent_runtime'])
def test_postgres_int4_range(store,table):
    db,uid,wid=store
    with pytest.raises(IntegrityError):
        with db.transaction() as session:
            row=(agent if table=='agent' else runtime)(session,wid)
            session.execute(text(f'UPDATE {table} SET max_concurrent_tasks=2147483648 WHERE id=:id'),dict(id=row['id']))


@pytest.mark.parametrize('value', ['["not-uuid"]','[1]','["00000000-0000-0000-0000-000000000000",[]]'])
def test_uuid_arrays_reject_invalid_elements(store,value):
    db,uid,wid=store
    with pytest.raises(IntegrityError):
        with db.transaction() as session:
            runtime(session,wid,shared_with=value)


def test_jsonb_nul_and_null_array_elements(store):
    db,uid,wid=store
    with pytest.raises(IntegrityError):
        with db.transaction() as session:
            agent(session,wid,custom_env='{"name":"bad\\u0000value"}')
    with db.transaction() as session:
        r=runtime(session,wid,shared_with='[null]')
        a=agent(session,wid,runtime_id=r['id'],composio_toolkit_allowlist='[null,"github"]')
        assert a['composio_toolkit_allowlist']=='[null,"github"]'


def test_same_system_identity_is_unique(store):
    db,uid,wid=store
    with db.transaction() as session:
        r=runtime(session,wid)
        agent(session,wid,owner_id=uid,runtime_id=r['id'],system_key='system')
    with pytest.raises(IntegrityError):
        with db.transaction() as session:
            row=agent(session,wid,name='Other',owner_id=uid,runtime_id=r['id'],system_key='system')
