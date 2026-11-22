"""Canonical skill assignments retain disabled entries and cascade correctly."""
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_agent_env import env
from test_runtime_list import runtimes


def test_skill_schema_defaults_uniqueness_and_cascade(env):
    client,app,workspace,ids,headers,agent=env
    with app.state.database.transaction() as session:
        row=session.execute(text("INSERT INTO skill(workspace_id,name) VALUES (:wid,'Fixture') RETURNING *"),dict(wid=workspace['id'])).mappings().one()
        skill=row['id']
        assert row['description']==row['content']=='' and row['config']=='{}'
        assert row['plugin_installation_id'] is None
        session.execute(text('INSERT INTO agent_skill(agent_id,skill_id) VALUES (:agent,:skill)'),dict(agent=agent,skill=skill))
        assert session.scalar(text('SELECT enabled FROM agent_skill'))==1
    with pytest.raises(IntegrityError),app.state.database.transaction() as session:
        session.execute(text('INSERT INTO agent_skill(agent_id,skill_id) VALUES (:agent,:skill)'),dict(agent=agent,skill=skill))
    with pytest.raises(IntegrityError),app.state.database.transaction() as session:
        session.execute(text('INSERT INTO agent_skill(agent_id,skill_id) VALUES (:agent,:skill)'),dict(agent=agent,skill=str(uuid4())))
    with app.state.database.transaction() as session:
        session.execute(text('DELETE FROM skill WHERE id=:id'),dict(id=skill))
        assert session.scalar(text('SELECT count(*) FROM agent_skill'))==0


def test_agent_skills_summary_retains_disabled_and_excludes_body(env):
    client,app,workspace,ids,headers,agent=env
    with app.state.database.transaction() as session:
        for name,enabled in [('Z skill',0),('A skill',1)]:
            skill=str(uuid4())
            session.execute(text("INSERT INTO skill(id,workspace_id,name,content,config) VALUES (:id,:wid,:name,'do not execute this skill',:config)"),dict(id=skill,wid=workspace['id'],name=name,config='{"z":1,"a":2}'))
            session.execute(text('INSERT INTO agent_skill(agent_id,skill_id,enabled) VALUES (:agent,:skill,:enabled)'),dict(agent=agent,skill=skill,enabled=enabled))
    response=client.get(f'/api/agents/{agent}/skills',headers=headers())
    assert response.status_code==200
    assert [r['name'] for r in response.json()]==['A skill','Z skill']
    assert [r['enabled'] for r in response.json()]==[True,False]
    assert all('content' not in r and 'labels' not in r for r in response.json())
    assert response.content.endswith(b'\n')
    assert client.get(f'/api/agents/{agent}/skills',headers=headers(ids[2])).status_code==404
    with app.state.database.transaction() as session:
        session.execute(text("UPDATE agent SET kind='system'"))
    assert client.get(f'/api/agents/{agent}/skills',headers=headers()).status_code==404


def test_agent_skills_empty_and_query_failure(env):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError
    client,app,workspace,ids,headers,agent=env
    response=client.get(f'/api/agents/{agent}/skills',headers=headers())
    assert response.content==b'[]\n'
    def fail(conn,cursor,statement,parameters,context,executemany):
        if 'JOIN agent_skill' in statement:
            raise OperationalError(statement,parameters,Exception('fixture query outage'))
    event.listen(app.state.database.engine,'before_cursor_execute',fail)
    try:
        response=client.get(f'/api/agents/{agent}/skills',headers=headers())
        assert response.status_code==500
        assert response.content==b'{"error":"failed to list agent skills"}\n'
    finally:event.remove(app.state.database.engine,'before_cursor_execute',fail)
