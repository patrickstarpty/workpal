"""Canonical session relationships required by attachment authorization."""
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_agent_env import env
from test_runtime_list import runtimes


def insert_session(session,workspace,user,agent,runtime=None):
    return dict(session.execute(text('''INSERT INTO chat_session(workspace_id,creator_id,agent_id,runtime_id)
        VALUES (:workspace,:user,:agent,:runtime) RETURNING *'''),
        dict(workspace=workspace,user=user,agent=agent,runtime=runtime)).mappings().one())


def test_session_defaults_and_runtime_unbind(env):
    client,app,workspace,ids,headers,agent=env
    with app.state.database.transaction() as session:
        runtime=session.scalar(text('SELECT id FROM agent_runtime LIMIT 1'))
        row=insert_session(session,workspace['id'],ids[1],agent,runtime)
        assert row['status']=='active' and row['title']=='' and row['is_agent_intro']==0
        assert row['last_read_at']==row['created_at']==row['updated_at']
        assert row['project_id'] is None and row['explicitly_created_at'] is None
        session.execute(text('DELETE FROM agent_runtime WHERE id=:id'),dict(id=runtime))
        assert session.scalar(text('SELECT runtime_id FROM chat_session')) is None
        assert session.scalar(text('SELECT count(*) FROM chat_session'))==1


@pytest.mark.parametrize('column',['agent_id','creator_id','workspace_id','runtime_id'])
def test_session_rejects_missing_relationship(env,column):
    client,app,workspace,ids,headers,agent=env
    with pytest.raises(IntegrityError),app.state.database.transaction() as session:
        row=insert_session(session,workspace['id'],ids[1],agent)
        session.execute(text(f'UPDATE chat_session SET {column}=:id'),dict(id=str(uuid4())))


def test_session_agent_delete_cascades_and_project_has_no_fk(env):
    client,app,workspace,ids,headers,agent=env
    with app.state.database.transaction() as session:
        row=insert_session(session,workspace['id'],ids[1],agent)
        session.execute(text('UPDATE chat_session SET project_id=:id'),dict(id=str(uuid4())))
        session.execute(text('DELETE FROM agent WHERE id=:id'),dict(id=agent))
        assert session.scalar(text('SELECT count(*) FROM chat_session'))==0


@pytest.mark.parametrize('column,value',[('status','deleted'),('is_agent_intro',2),('title',None)])
def test_session_checks(env,column,value):
    client,app,workspace,ids,headers,agent=env
    with pytest.raises(IntegrityError),app.state.database.transaction() as session:
        insert_session(session,workspace['id'],ids[1],agent)
        session.execute(text(f'UPDATE chat_session SET {column}=:value'),dict(value=value))


def test_session_shape_matches_frozen_catalog(env):
    import json
    from pathlib import Path
    from sqlalchemy import inspect
    client,app,workspace,ids,headers,agent=env
    catalog=json.loads((Path(__file__).resolve().parents[2]/'docs/superpowers/evidence/2026-11-22-go-reference-schema.json').read_text())
    expected=[row for row in catalog['columns'] if row['table_name']=='chat_session']
    inspector=inspect(app.state.database.engine)
    actual=inspector.get_columns('chat_session')
    assert [(c['name'],c['nullable']) for c in actual]==[(c['column_name'],c['is_nullable']=='YES') for c in expected]
    assert {i['name'] for i in inspector.get_indexes('chat_session')}=={i['name'] for i in catalog['indexes'] if i['table_name']=='chat_session' and i['name']!='chat_session_pkey'}
    assert {(tuple(f['constrained_columns']),f['referred_table'],f['options'].get('ondelete')) for f in inspector.get_foreign_keys('chat_session')}=={
        (('workspace_id',),'workspaces','CASCADE'),(('creator_id',),'users','CASCADE'),
        (('agent_id',),'agent','CASCADE'),(('runtime_id',),'agent_runtime','SET NULL')}
