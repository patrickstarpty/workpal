"""Read adapters use actual SQL; fixture tables are not application migrations."""
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from workpal_backend.projects.queries import ProjectQueries
from workpal_backend.projects.access import for_principals,NoRows
from workpal_backend.realtime.private_projects import PrivateProjectAudience
from workpal_backend.realtime.task_projects import tasks_projects

def uid(i):return f'00000000-0000-0000-0000-{i:012x}'
W,OTHER,P,P2,U,V,I,C,R,A,T=[uid(i) for i in range(1,12)]

@pytest.fixture
def query():
    engine=create_engine('sqlite://')
    with engine.begin() as c:
        for sql in [
          'CREATE TABLE project(id TEXT PRIMARY KEY,workspace_id TEXT,visibility TEXT)',
          'CREATE TABLE project_member(workspace_id TEXT,project_id TEXT,user_id TEXT)',
          'CREATE TABLE members(id TEXT,workspace_id TEXT,user_id TEXT,role TEXT)',
          'CREATE TABLE issue(id TEXT PRIMARY KEY,project_id TEXT)',
          'CREATE TABLE comment(id TEXT PRIMARY KEY,issue_id TEXT)',
          'CREATE TABLE autopilot(id TEXT PRIMARY KEY,project_id TEXT)',
          'CREATE TABLE autopilot_run(id TEXT PRIMARY KEY,autopilot_id TEXT)',
          'CREATE TABLE agent_task_queue(id TEXT PRIMARY KEY,issue_id TEXT,chat_session_id TEXT,autopilot_run_id TEXT,context TEXT)',
        ]:c.execute(text(sql))
        for sql,params in [
          ('INSERT INTO project VALUES (:p,:w,\'private\'),(:p2,:w,\'private\'),(:other,:other,\'private\')',dict(p=P,p2=P2,w=W,other=OTHER)),
          ('INSERT INTO project_member VALUES (:w,:p,:u),(:other,:p,:v)',dict(w=W,p=P,u=U,v=V,other=OTHER)),
          ('INSERT INTO members VALUES (:u,:w,:u,\'owner\'),(:v,:w,:v,\'member\')',dict(u=U,v=V,w=W)),
          ('INSERT INTO issue VALUES (:i,:p)',dict(i=I,p=P)),
          ('INSERT INTO comment VALUES (:c,:i)',dict(c=C,i=I)),
          ('INSERT INTO autopilot VALUES (:a,:p)',dict(a=A,p=P2)),
          ('INSERT INTO autopilot_run VALUES (:r,:a)',dict(r=R,a=A)),
          ('INSERT INTO agent_task_queue(id,issue_id) VALUES (:t,:i)',dict(t=T,i=I)),
        ]:c.execute(text(sql),params)
    with Session(engine) as session:yield ProjectQueries(session),session
    engine.dispose()


def test_hidden_and_audience_queries_match_join_not_invented_workspace_filter(query):
    q,s=query
    assert set(q.list_private_project_ids(W))=={P,P2}
    assert q.list_hidden_project_ids(W,U)==[P2]
    # Go's NOT EXISTS/join deliberately uses project_id/user_id, not pm.workspace_id.
    assert q.list_hidden_project_ids(W,V)==[P2]
    assert set(q.list_private_project_audience(W))=={(P,U),(P,V),(P2,None)}
    assert for_principals(q,W,U).ids()==[P2]
    assert for_principals(q,W,uid(99)).ids()==[P,P2]


def test_lookup_null_missing_batch_and_task_resolution(query):
    q,s=query
    assert q.issue_project(I)==P and q.comment_project(C)==P and q.autopilot_project(A)==P2
    assert tasks_projects(q,[q.get_task(T),{'autopilot_run_id':R}])==[[P],[P2]]
    assert q.list_issue_project_ids([])==[] and q.list_autopilot_run_project_ids([])==[]
    assert q.list_issue_project_ids([I,I,uid(99)])==[(I,P)]
    s.execute(text('UPDATE issue SET project_id=NULL'))
    assert q.issue_project(I) is None
    for method in [q.issue_project,q.comment_project,q.autopilot_project,q.get_task]:
        with pytest.raises(NoRows):method(uid(99))


def test_audience_reloads_after_membership_removal_event(query):
    q,s=query;a=PrivateProjectAudience(q)
    event=dict(type='task:message',workspaceID=W,taskID=T,payload={})
    assert a(event)==([U,V],True)
    s.execute(text('DELETE FROM project_member WHERE user_id=:u'),{'u':U})
    a(dict(type='project:members_changed',workspaceID=W,payload={'project_id':P}))
    assert a(event)==([V],True)
    s.execute(text('DROP TABLE project_member'))
    with pytest.raises(OperationalError):q.list_private_project_audience(W)


def test_agent_run_query_adapter_observes_owner_and_originator_changes(query):
    from workpal_backend.projects.request_access import hidden_for_agent_run
    q,s=query
    s.execute(text('CREATE TABLE agent(id TEXT PRIMARY KEY,workspace_id TEXT,owner_id TEXT)'))
    s.execute(text('INSERT INTO agent VALUES (:a,:w,:owner)'),{'a':A,'w':W,'owner':V})
    s.execute(text('ALTER TABLE agent_task_queue ADD COLUMN originator_user_id TEXT'))
    s.execute(text('ALTER TABLE agent_task_queue ADD COLUMN accountable_user_id TEXT'))
    s.execute(text('UPDATE agent_task_queue SET originator_user_id=:u,accountable_user_id=:v'),{'u':U,'v':V})
    assert hidden_for_agent_run(q,W,A,T).ids()==[P2]
    s.execute(text('UPDATE agent SET owner_id=:outsider'),{'outsider':uid(99)})
    assert set(hidden_for_agent_run(q,W,A,T).ids())=={P,P2}
    s.execute(text('UPDATE agent SET owner_id=NULL'))
    s.execute(text('UPDATE agent_task_queue SET originator_user_id=NULL'))
    assert hidden_for_agent_run(q,W,A,T).ids()==[P2]
    s.execute(text('DELETE FROM agent'))
    assert set(hidden_for_agent_run(q,W,A,T).ids())=={P,P2}


def test_attachment_parent_filter_queries_are_workspace_scoped(query):
    from workpal_backend.files.access import visible_attachment_ids
    from workpal_backend.projects.access import Hidden
    q,s=query
    s.execute(text('CREATE TABLE attachment(id TEXT PRIMARY KEY,workspace_id TEXT,issue_id TEXT,comment_id TEXT,created_at TEXT)'))
    a1,a2,a3=uid(101),uid(102),uid(103)
    s.execute(text('INSERT INTO attachment VALUES (:a,:w,:i,NULL,\'2020\'),(:b,:w,NULL,:c,\'2021\'),(:x,:other,:i,NULL,\'2022\')'),dict(a=a1,b=a2,x=a3,w=W,other=OTHER,i=I,c=C))
    hidden=Hidden();hidden.add([P])
    ids=[a2,a1,a3,uid(99),a1]
    assert visible_attachment_ids(q,hidden,W,ids)==[a3,uid(99)]
    s.execute(text('DELETE FROM comment'))
    assert visible_attachment_ids(q,hidden,W,ids)==[a2,a3,uid(99)]
    assert q.list_attachments_by_ids(W,[])==[]


def test_actor_query_adapter_normalizes_stored_task_agent_uuid(query):
    from workpal_backend.auth.actor import resolve_actor
    q,s=query
    s.execute(text('CREATE TABLE agent(id TEXT PRIMARY KEY,workspace_id TEXT,owner_id TEXT)'))
    s.execute(text('INSERT INTO agent VALUES (:a,:w,NULL)'),{'a':A,'w':W})
    s.execute(text('ALTER TABLE agent_task_queue ADD COLUMN agent_id TEXT'))
    s.execute(text('UPDATE agent_task_queue SET agent_id=:agent'),{'agent':A.upper()})
    assert resolve_actor(q,U,W,agent_id=A,task_id=T)==('agent',A)


def test_attachment_load_queries_preserve_scope_and_nullable_parent(query):
    q,s=query
    s.execute(text('CREATE TABLE attachment(id TEXT PRIMARY KEY,workspace_id TEXT,issue_id TEXT,comment_id TEXT,filename TEXT)'))
    s.execute(text('INSERT INTO attachment VALUES (:a,:w,:i,NULL,\'report.txt\')'),dict(a=A,w=W,i=I))
    assert q.get_attachment(A,W)==dict(id=A,workspace_id=W,issue_id=I,comment_id=None,filename='report.txt')
    assert q.get_attachment_by_id(A)==q.get_attachment(A,W)
    with pytest.raises(NoRows):q.get_attachment(A,OTHER)
    with pytest.raises(NoRows):q.get_attachment_by_id(uid(999))


def test_public_chat_projection_excludes_command_only_but_keeps_explicit_empty_sessions(query):
    q,s=query
    s.execute(text('CREATE TABLE chat_session(id TEXT PRIMARY KEY,workspace_id TEXT,agent_id TEXT,creator_id TEXT,explicitly_created_at TEXT)'))
    s.execute(text('CREATE TABLE chat_message(chat_session_id TEXT,message_kind TEXT)'))
    s.execute(text('INSERT INTO chat_session VALUES (:id,:w,:a,:u,NULL)'),dict(id=T,w=W,a=A,u=U))
    assert q.get_chat_session_in_workspace(T,W)['creator_id']==U
    with pytest.raises(NoRows):q.get_chat_session_in_workspace(T,OTHER)
    with pytest.raises(NoRows):q.get_public_chat_session_in_workspace(T,W)
    s.execute(text('INSERT INTO chat_message VALUES (:id,\'channel_command\'),(:id,NULL)'),dict(id=T))
    with pytest.raises(NoRows):q.get_public_chat_session_in_workspace(T,W)
    s.execute(text('INSERT INTO chat_message VALUES (:id,\'message\')'),dict(id=T))
    assert q.get_public_chat_session_in_workspace(T,W)['id']==T
    s.execute(text('DELETE FROM chat_message'))
    s.execute(text('UPDATE chat_session SET explicitly_created_at=\'2026-11-22T00:00:00Z\''))
    assert q.get_public_chat_session_in_workspace(T,W)['id']==T


def test_agent_invocation_target_queries_are_agent_scoped_and_ordered(query):
    q,s=query
    s.execute(text('CREATE TABLE agent_invocation_target(id TEXT,agent_id TEXT,target_type TEXT,target_id TEXT,created_by TEXT,created_at TEXT)'))
    s.execute(text('INSERT INTO agent_invocation_target VALUES (:i,:a,\'workspace\',NULL,:u,\'2020\'),(:c,:a,\'member\',:v,:u,\'2021\'),(:t,:other,\'member\',:u,:u,\'2019\')'),dict(i=I,c=C,t=T,a=A,other=OTHER,u=U,v=V))
    targets=q.list_agent_invocation_targets(A)
    assert [target['id'] for target in targets]==[C,I]
    assert targets[0]['target_id']==V and targets[1]['target_id'] is None


def test_task_upload_lookup_uses_agent_workspace_join(query):
    q,s=query
    s.execute(text('CREATE TABLE agent(id TEXT PRIMARY KEY,workspace_id TEXT)'))
    s.execute(text('INSERT INTO agent VALUES (:a,:w)'),dict(a=A,w=W))
    s.execute(text('ALTER TABLE agent_task_queue ADD COLUMN agent_id TEXT'))
    s.execute(text('UPDATE agent_task_queue SET agent_id=:a,chat_session_id=:s'),dict(a=A,s=C))
    assert q.get_task_in_workspace(T,W)['chat_session_id']==C
    with pytest.raises(NoRows):q.get_task_in_workspace(T,OTHER)
    s.execute(text('DELETE FROM agent'))
    with pytest.raises(NoRows):q.get_task_in_workspace(T,W)


def test_upload_issue_and_comment_queries_keep_scope_and_tombstones(query):
    q,s=query
    s.execute(text('ALTER TABLE issue ADD COLUMN workspace_id TEXT'))
    s.execute(text('UPDATE issue SET workspace_id=:w'),dict(w=W))
    s.execute(text('ALTER TABLE comment ADD COLUMN workspace_id TEXT'))
    s.execute(text('ALTER TABLE comment ADD COLUMN deleted_at TEXT'))
    s.execute(text('UPDATE comment SET workspace_id=:w,deleted_at=\'2026-11-22T00:00:00Z\''),dict(w=W))
    assert q.get_issue_in_workspace(I,W)['project_id']==P
    with pytest.raises(NoRows):q.get_issue_in_workspace(I,OTHER)
    assert q.get_comment(C)['deleted_at']=='2026-11-22T00:00:00Z'
    assert q.get_comment(C)['workspace_id']==W
    with pytest.raises(NoRows):q.get_comment(uid(999))


def test_comment_event_queries_scope_attachments_but_group_reactions_by_parent_only(query):
    q,s=query
    s.execute(text('ALTER TABLE comment ADD COLUMN workspace_id TEXT'))
    s.execute(text('UPDATE comment SET workspace_id=:w'),dict(w=W))
    assert q.get_comment_in_workspace(C,W)['issue_id']==I
    with pytest.raises(NoRows):q.get_comment_in_workspace(C,OTHER)
    s.execute(text('CREATE TABLE attachment(id TEXT,workspace_id TEXT,comment_id TEXT,chat_message_id TEXT,created_at TEXT)'))
    s.execute(text('INSERT INTO attachment VALUES (:a,:w,:c,:c,\'2021\'),(:b,:w,:c,:c,\'2020\'),(:x,:other,:c,:c,\'2019\')'),dict(a=A,b=T,x=R,w=W,c=C,other=OTHER))
    assert [r['id'] for r in q.list_attachments_by_comment_ids([C],W)]==[T,A]
    assert [r['id'] for r in q.list_attachments_by_chat_message_ids([C],W)]==[T,A]
    s.execute(text('CREATE TABLE comment_reaction(id TEXT,comment_id TEXT,workspace_id TEXT,actor_id TEXT,created_at TEXT)'))
    s.execute(text('INSERT INTO comment_reaction VALUES (:a,:c,:w,:u,\'2021\'),(:b,:c,:other,:v,\'2020\')'),dict(a=A,b=T,c=C,w=W,other=OTHER,u=U,v=V))
    assert [r['id'] for r in q.list_reactions_by_comment_ids([C])]==[T,A]
    assert q.list_reactions_by_comment_ids([])==[]


def test_attachment_inventory_filters_issue_workspace_and_deleted_origins(query):
    q,s=query
    s.execute(text('CREATE TABLE attachment(id TEXT,workspace_id TEXT,issue_id TEXT,created_at TEXT)'))
    s.execute(text("INSERT INTO attachment VALUES (:a,:w,:i,'2021'),(:t,:w,:i,'2020'),(:r,:other,:i,'2019'),(:c,:w,:other,'2018')"),dict(a=A,t=T,r=R,c=C,w=W,i=I,other=OTHER))
    assert [row['id'] for row in q.list_attachments_by_issue(I,W)]==[T,A]
    for column in ('workspace_id','author_type','author_id','created_at','deleted_at'):
        s.execute(text(f'ALTER TABLE comment ADD COLUMN {column} TEXT'))
    s.execute(text("UPDATE comment SET workspace_id=:w,author_type='member',author_id=:u"),dict(w=W,u=U))
    assert q.list_comment_origins_for_issue([C],I,W)==[dict(id=C,author_type='member',author_id=U,created_at=None)]
    assert q.list_comment_origins_for_issue([C],I,OTHER)==[]
    assert q.list_comment_origins_for_issue([C],OTHER,W)==[]
    assert q.list_comment_origins_for_issue([],I,W)==[]
    s.execute(text("UPDATE comment SET deleted_at='2026-11-22'"))
    assert q.list_comment_origins_for_issue([C],I,W)==[]


def test_issue_identifier_lookup_scopes_number_and_normalizes_workspace(query):
    q,s=query
    s.execute(text('CREATE TABLE workspace(id TEXT,name TEXT,issue_prefix TEXT)'))
    s.execute(text("INSERT INTO workspace VALUES (:w,'Workpal','WP')"),dict(w=W))
    s.execute(text('ALTER TABLE issue ADD COLUMN workspace_id TEXT'))
    s.execute(text('ALTER TABLE issue ADD COLUMN number INTEGER'))
    s.execute(text('UPDATE issue SET workspace_id=:w,number=42'),dict(w=W))
    assert q.get_workspace(W)==dict(id=W,name='Workpal',issue_prefix='WP')
    assert q.get_issue_by_number(W,42)['id']==I
    with pytest.raises(NoRows):q.get_workspace(OTHER)
    with pytest.raises(NoRows):q.get_issue_by_number(OTHER,42)
    with pytest.raises(NoRows):q.get_issue_by_number(W,43)
