"""Project changes must remain discoverable across commits, deletes and rollback."""
import pytest
from sqlalchemy import text
from test_agent_env import env
from test_runtime_list import runtimes


def add(session,workspace,title='Fixture'):
    return session.scalar(text('INSERT INTO project(workspace_id,title) VALUES (:workspace,:title) RETURNING id'),dict(workspace=workspace,title=title))


def test_changes_share_transaction_identity_and_retain_deletion(env):
    client,app,workspace,ids,headers,agent=env
    with app.state.database.transaction() as session:
        before=session.scalar(text('SELECT workpal_current_snapshot()'))
        one=add(session,workspace['id'])
        two=add(session,workspace['id'],'Second')
        session.execute(text('UPDATE project SET title=title WHERE id=:id'),dict(id=one))
        changes=session.execute(text('SELECT * FROM search_index_change ORDER BY entity_id')).mappings().all()
        assert len(changes)==2
        assert changes[0]['change_xid']==changes[1]['change_xid']
        assert changes[0]['changed_at']==changes[1]['changed_at']
    with app.state.database.transaction() as session:
        after=session.scalar(text('SELECT workpal_current_snapshot()'))
        xid=changes[0]['change_xid']
        assert session.scalar(text('SELECT workpal_visible_in_snapshot(:x,:s)'),dict(x=xid,s=before))==0
        assert session.scalar(text('SELECT workpal_visible_in_snapshot(:x,:s)'),dict(x=xid,s=after))==1
        session.execute(text('DELETE FROM project WHERE id=:id'),dict(id=one))
    with app.state.database.transaction() as session:
        rows=session.execute(text('SELECT * FROM search_index_change')).mappings().all()
        assert len(rows)==2
        deleted=next(r for r in rows if r['entity_id']==one)
        assert deleted['change_xid']>xid
        assert session.scalar(text('SELECT count(*) FROM project WHERE id=:id'),dict(id=one))==0


def test_project_and_change_record_roll_back_together(env):
    client,app,workspace,ids,headers,agent=env
    with pytest.raises(RuntimeError),app.state.database.transaction() as session:
        add(session,workspace['id'])
        raise RuntimeError('fixture rollback')
    with app.state.database.transaction() as session:
        assert session.scalar(text('SELECT count(*) FROM project'))==0
        assert session.scalar(text('SELECT count(*) FROM search_index_change'))==0


def test_project_teardown_suppression_is_transaction_local(env):
    client,app,workspace,ids,headers,agent=env
    with app.state.database.transaction() as session:
        session.connection().info.setdefault('transaction_settings',{})['workpal.workspace_teardown']='on'
        add(session,workspace['id'])
        assert session.scalar(text('SELECT count(*) FROM search_index_change'))==0
    with app.state.database.transaction() as session:
        add(session,workspace['id'])
        assert session.scalar(text('SELECT count(*) FROM search_index_change'))==1


def test_savepoint_rollback_does_not_reuse_a_committed_change_id(env):
    client,app,workspace,ids,headers,agent=env
    with app.state.database.transaction() as session:
        # Establish the physical outer transaction before rolling back only
        # the savepoint that first allocated a search transaction identifier.
        session.execute(text("UPDATE agent SET name=name"))
        nested=session.begin_nested()
        add(session,workspace['id'],'Rolled back')
        nested.rollback()
        first=add(session,workspace['id'],'Committed')
        xid=session.scalar(text('SELECT change_xid FROM search_index_change WHERE entity_id=:id'),dict(id=first))
    with app.state.database.transaction() as session:
        second=add(session,workspace['id'],'Later')
        later=session.scalar(text('SELECT change_xid FROM search_index_change WHERE entity_id=:id'),dict(id=second))
        assert later>xid


def test_snapshot_taken_during_writer_does_not_lose_later_commit(env):
    client,app,workspace,ids,headers,agent=env
    database=app.state.database
    with database.transaction() as writer:
        project=add(writer,workspace['id'])
        xid=writer.scalar(text('SELECT change_xid FROM search_index_change WHERE entity_id=:id'),dict(id=project))
        with database.transaction() as reader:
            before=reader.scalar(text('SELECT workpal_current_snapshot()'))
            assert reader.scalar(text('SELECT count(*) FROM project'))==0
            assert reader.scalar(text('SELECT workpal_visible_in_snapshot(:x,:s)'),dict(x=xid,s=before))==0
    with database.transaction() as reader:
        after=reader.scalar(text('SELECT workpal_current_snapshot()'))
        assert reader.scalar(text('SELECT count(*) FROM project'))==1
        assert reader.scalar(text('SELECT workpal_visible_in_snapshot(:x,:s)'),dict(x=xid,s=after))==1


def test_first_operation_savepoint_still_rolls_back_with_outer_transaction(env):
    client,app,workspace,ids,headers,agent=env
    database=app.state.database
    with pytest.raises(RuntimeError),database.transaction() as session:
        with session.begin_nested():add(session,workspace['id'])
        raise RuntimeError('outer rollback')
    with database.transaction() as session:
        assert session.scalar(text('SELECT count(*) FROM project'))==0
        assert session.scalar(text('SELECT count(*) FROM search_index_change'))==0
