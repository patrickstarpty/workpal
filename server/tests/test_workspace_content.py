"""HTTP contracts for preserved local content and workspace authorization."""
from urllib.parse import quote
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate
from workpal_backend.workspaces import service
from workpal_backend.workspaces.models import issue_status


@pytest.fixture
def content(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login = client.post('/auth/verify-code', json={'email': 'dev@workpal.local', 'code': '888888'}).json()
        authorization = {'Authorization': 'Bearer ' + login['token']}
        workspace = client.post('/api/workspaces', json={'name': 'TAP', 'slug': 'tap', 'issue_prefix': 'TAP'}, headers=authorization).json()
        yield app, client, authorization | {'X-Workspace-Slug': 'tap'}, workspace


def seed(app, workspace, kind, rows):
    from workpal_backend.workspace_content.models import records
    with app.state.database.transaction() as session:
        for position, body in enumerate(rows):
            session.execute(records.insert().values(workspace_id=workspace['id'], kind=kind,
                                                   id=body['id'], body=body, position=position))


def test_crud_uses_authenticated_identity_and_persists(content, settings):
    app, client, headers, workspace = content
    response = client.post('/api/projects', headers=headers, json={
        'title': 'TAP roadmap', 'description': '<script>literal text</script>',
        'id': 'forged', 'workspace_id': 'foreign', 'creator_id': 'forged', 'creator_type': 'agent',
    })
    assert response.status_code == 201, response.text
    project = response.json()
    assert project['id'] != 'forged'
    assert project['workspace_id'] == workspace['id']
    assert project['creator_type'] == 'member'
    assert project['creator_id'] == client.get('/api/me', headers=headers).json()['id']
    assert project['description'] == '<script>literal text</script>'
    changed = client.patch('/api/projects/' + project['id'], headers=headers, json={
        'title': 'TAP launch', 'creator_id': 'forged', 'workspace_id': 'other', 'id': 'other',
    })
    assert changed.status_code == 200
    assert changed.json()['creator_id'] == project['creator_id']
    assert changed.json()['id'] == project['id']
    assert client.get('/api/projects', headers=headers).json()['projects'][0]['title'] == 'TAP launch'
    with TestClient(create_app(settings)) as reopened:
        assert reopened.get('/api/projects/' + project['id'], headers=headers).json()['title'] == 'TAP launch'
        assert reopened.delete('/api/projects/' + project['id'], headers=headers).status_code == 200
    assert client.get('/api/projects/' + project['id'], headers=headers).status_code == 404


def test_every_workspace_operation_requires_explicit_membership(content):
    app, client, headers, workspace = content
    token = {'Authorization': headers['Authorization']}
    assert client.get('/api/projects', headers=token).status_code == 400
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/projects', headers={'X-Workspace-Slug': 'tap'}).status_code == 401
    from workpal_backend.auth.models import users
    with app.state.database.transaction() as session:
        outsider = str(uuid4())
        session.execute(users.insert().values(id=outsider, email='other@example.com', name='Other',
                                             created_at='2026-01-01T00:00:00Z', updated_at='2026-01-01T00:00:00Z'))
        foreign = service.create_workspace(session, outsider, 'Private', 'private-space')
    seed(app, foreign, 'projects', [{'id': 'secret', 'title': 'Private plan'}])
    seed(app, foreign, 'issues', [{'id': 'private-issue', 'identifier': 'PRIVATE-1', 'title': 'Secret'}])
    private = token | {'X-Workspace-Slug': foreign['slug']}
    assert client.get('/api/issues/PRIVATE-1', headers=private).status_code == 404
    assert client.post('/api/issues/private-issue/comments', headers=private, json={'content': 'intrusion'}).status_code == 404
    for path in ('/api/properties', '/api/inbox/snoozed', '/api/inbox/unread-summary', '/api/working-agents', '/api/agent-activity-30d', '/api/search-index/manifest'):
        assert client.get(path, headers=private).status_code == 404
    for path in ('/api/projects', '/api/projects/secret', '/api/issue-statuses', '/api/runtimes', '/api/chat/sessions', '/api/issue-view-preferences'):
        assert client.get(path, headers=token | {'X-Workspace-Slug': foreign['slug']}).status_code == 404
    # Exercise the ID fallback against a real private workspace, not an unknown UUID.
    private_headers = token | {'X-Workspace-ID': foreign['id']}
    assert client.get('/api/projects', headers=private_headers).status_code == 404
    assert client.get('/api/projects/secret', headers=private_headers).status_code == 404
    assert client.post('/api/projects', headers=private_headers, json={'title': 'Intrusion'}).status_code == 404
    assert client.patch('/api/projects/secret', headers=private_headers, json={'title': 'Intrusion'}).status_code == 404
    assert client.delete('/api/projects/secret', headers=private_headers).status_code == 404
    from workpal_backend.workspace_content import repository
    with app.state.database.transaction() as session:
        assert repository.get_record(session, foreign['id'], 'projects', 'secret')['title'] == 'Private plan'
    assert client.get('/api/projects/secret', headers=headers).status_code == 404
    assert client.patch('/api/projects/secret', headers=headers, json={'title': 'stolen'}).status_code == 404
    assert client.delete('/api/projects/secret', headers=headers).status_code == 404
    assert client.get('/api/projects', headers=headers).json() == {'projects': [], 'total': 0}


def test_preserved_tap_ids_issue_details_and_search(content):
    app, client, headers, workspace = content
    project_id, issue_id = 'TAP original/project', 'TAP issue/17'
    seed(app, workspace, 'projects', [{'id': project_id, 'title': 'TAP', 'description': 'Original project notes'}])
    seed(app, workspace, 'issues', [
        {'id': issue_id, 'title': 'Original TAP task', 'identifier': 'TAP-17', 'status': 'in_progress',
         'project_id': project_id, 'parent_issue_id': None, 'labels': [{'id': 'urgent', 'name': 'Urgent'}], 'sub_issue_count': 1},
        {'id': 'child', 'title': 'Child', 'identifier': 'TAP-18', 'status': 'done', 'project_id': project_id,
         'parent_issue_id': issue_id},
    ])
    seed(app, workspace, 'comments', [
        {'id': 'comment-later', 'issue_id': issue_id, 'body': 'Later notes', 'created_at': '2026-02-02', 'type': 'normal', 'author_type': 'member', 'author_id': 'member'},
        {'id': 'comment-first', 'issue_id': issue_id, 'body': 'Original notes', 'created_at': '2026-02-01', 'type': 'normal', 'author_type': 'member', 'author_id': 'member'},
    ])
    path = '/api/issues/' + quote(issue_id, safe='')
    assert client.get('/api/projects/' + quote(project_id, safe=''), headers=headers).json()['title'] == 'TAP'
    assert client.get(path, headers=headers).json()['identifier'] == 'TAP-17'
    assert [row['id'] for row in client.get(path + '/comments', headers=headers).json()] == ['comment-first', 'comment-later']
    timeline = client.get(path + '/timeline', headers=headers).json()
    assert timeline[0]['type'] == 'comment' and timeline[0]['actor_type'] == 'member'
    assert client.get(path + '/children', headers=headers).json()['issues'][0]['id'] == 'child'
    assert client.get(path + '/labels', headers=headers).json() == [{'id': 'urgent', 'name': 'Urgent'}]
    assert client.get('/api/issues/child-progress', headers=headers).json() == {'progress': [{'parent_issue_id': issue_id, 'total': 1, 'done': 1}]}
    assert client.get('/api/issues/search?q=TAP-17', headers=headers).json()['issues'][0]['id'] == issue_id
    assert client.get('/api/projects/search?q=notes', headers=headers).json()['projects'][0]['id'] == project_id


def test_issue_table_preserves_filters_groups_and_hierarchy(content):
    app, client, headers, workspace = content
    seed(app, workspace, 'issues', [
        {'id': 'one', 'title': 'TAP first', 'identifier': 'TAP-1', 'status': 'todo', 'priority': 'high', 'project_id': 'p', 'parent_issue_id': None},
        {'id': 'two', 'title': 'TAP child', 'identifier': 'TAP-2', 'status': 'done', 'priority': 'low', 'project_id': 'p', 'parent_issue_id': 'one'},
        {'id': 'three', 'title': 'Other', 'identifier': 'X-3', 'status': 'todo', 'priority': 'high', 'project_id': 'q', 'parent_issue_id': None},
    ])
    body = {'query': {'scope': {'project_id': 'p'}, 'search': 'tap', 'filters': {'statuses': ['todo'], 'priorities': ['high']}}, 'hierarchy': {'enabled': True}}
    rows = client.post('/api/issues/table/rows', headers=headers, json=body).json()
    assert rows['total'] == 1 and rows['rows'][0]['issue']['id'] == 'one'
    groups = client.post('/api/issues/table/groups', headers=headers, json={'query': {'scope': {'project_id': 'p'}}}).json()
    assert groups['groups'] == [{'key': 'status:todo', 'value': {'kind': 'status', 'status': 'todo'}, 'count': 1}, {'key': 'status:done', 'value': {'kind': 'status', 'status': 'done'}, 'count': 1}]
    assert client.post('/api/issues/table/rows', headers=headers, json={'group_key': 'status/done'}).json()['rows'][0]['issue']['id'] == 'two'


@pytest.mark.parametrize(('kind', 'field'), [('issues', 'title'), ('projects', 'title'), ('agents', 'name'), ('skills', 'name'), ('squads', 'name'), ('autopilots', 'title'), ('labels', 'name')])
def test_collection_crud_and_validation(content, kind, field):
    _, client, headers, workspace = content
    assert client.post('/api/' + kind, headers=headers, json={field: ''}).status_code == 400
    assert client.post('/api/' + kind, headers=headers, json={field: 'New', 'description': {}}).status_code == 400
    created = client.post('/api/' + kind, headers=headers, json={field: 'New'}).json()
    path = '/api/' + kind + '/' + created['id']
    assert client.get(path, headers=headers).json()[field] == 'New'
    assert client.put(path, headers=headers, json={field: 'Updated'}).json()[field] == 'Updated'
    assert client.delete(path, headers=headers).status_code == 200
    assert client.get(path, headers=headers).status_code == 404


def test_native_statuses_preferences_and_preserved_runtime_session_squad(content, settings):
    app, client, headers, workspace = content
    with app.state.database.transaction() as session:
        native = {row.id for row in session.execute(select(issue_status.c.id).where(issue_status.c.workspace_id == workspace['id']))}
    statuses = client.get('/api/issue-statuses', headers=headers).json()
    assert {row['id'] for row in statuses['statuses']} == native
    seed(app, workspace, 'runtimes', [{'id': 'runtime/old', 'name': 'Original runtime', 'status': 'offline'}])
    seed(app, workspace, 'sessions', [{'id': 'session-old', 'title': 'Original chat'}])
    seed(app, workspace, 'squads', [{'id': 'squad/old', 'name': 'Original squad', 'created_at': '2026-01-01', 'member_preview': [{'member_type': 'agent', 'member_id': 'agent-old', 'name': 'Assistant'}]}])
    assert client.get('/api/runtimes/runtime%2Fold', headers=headers).json()['name'] == 'Original runtime'
    assert client.get('/api/chat/sessions', headers=headers).json()[0]['title'] == 'Original chat'
    assert client.get('/api/squads/squad%2Fold/members', headers=headers).json()[0]['squad_id'] == 'squad/old'
    assert client.get('/api/squads/squad%2Fold/members/status', headers=headers).json()['members'][0]['status'] == 'offline'
    preference = {'scope': 'projects_page', 'preferences': {'sort': 'title'}}
    assert client.put('/api/issue-view-preferences', headers=headers, json=preference).json() == preference
    with TestClient(create_app(settings)) as reopened:
        assert reopened.get('/api/issue-view-preferences', headers=headers).json() == preference


def test_unsupported_execution_and_missing_subresources_fail_explicitly(content):
    app, client, headers, workspace = content
    seed(app, workspace, 'agents', [{'id': 'agent', 'name': 'Assistant'}])
    for path in ('/api/agents/agent/run', '/api/skills/install', '/api/chat/sessions', '/api/runtimes/execute'):
        response = client.post(path, headers=headers, json={'command': 'touch /tmp/never-execute-user-input'})
        assert response.status_code == 501, (path, response.text)
    assert client.get('/api/projects/missing/resources', headers=headers).status_code == 404
    assert client.get('/api/issues/missing/comments', headers=headers).status_code == 404
    assert client.get('/api/agents/agent/arbitrary-operation', headers=headers).status_code != 200
    assert client.get('/api/agent-task-snapshot', headers=headers).json() == []
    assert client.get('/api/chat/pending-tasks', headers=headers).json() == {'tasks': []}


def test_malformed_values_never_write_records(content):
    _, client, headers, _ = content
    for raw in ('null', '[]', '{', '{"title":"Bad", "metadata":{"value":NaN}}'):
        response = client.post('/api/projects', headers=headers, content=raw)
        assert response.status_code == 400
    assert client.get('/api/projects', headers=headers).json()['total'] == 0


def test_compound_missing_id_and_cross_workspace_references(content):
    app, client, headers, workspace = content
    other = client.post('/api/workspaces', headers=headers, json={'name': 'Other', 'slug': 'other-space'}).json()
    seed(app, other, 'projects', [{'id': 'foreign/project', 'title': 'Private'}])
    seed(app, other, 'issues', [{'id': 'foreign/issue', 'title': 'Private task'}])
    for field, record_id in (('project_id', 'foreign/project'), ('parent_issue_id', 'foreign/issue')):
        response = client.post('/api/issues', headers=headers, json={'title': 'Leak', field: record_id})
        assert response.status_code == 404
    for method in ('GET', 'PATCH', 'DELETE'):
        assert client.request(method, '/api/issues/foreign%2Fissue', headers=headers,
                              **({'json': {'title': 'Leak'}} if method == 'PATCH' else {})).status_code == 404
    assert client.get('/api/issues', headers=headers).json()['total'] == 0


def test_preferences_are_personal_and_match_frontend_scope_keys(content, settings):
    app, client, headers, workspace = content
    preference = {'scope_type': 'projects_page', 'scope_id': 'some/project', 'prefs': {'sort': 'title'}}
    assert client.put('/api/issue-view-preferences', headers=headers, json=preference).status_code == 200
    query = '/api/issue-view-preferences?scope_type=projects_page&scope_id=some%2Fproject'
    assert client.get(query, headers=headers).json() == preference
    from workpal_backend.auth.models import users
    from workpal_backend.workspaces.models import members
    with app.state.database.transaction() as session:
        other_id = str(uuid4())
        session.execute(users.insert().values(id=other_id, email='colleague@example.com', name='Colleague',
                                             created_at='2026-01-01T00:00:00Z', updated_at='2026-01-01T00:00:00Z'))
        session.execute(members.insert().values(id=str(uuid4()), workspace_id=workspace['id'], user_id=other_id,
                                               role='member', created_at='2026-01-01T00:00:00Z'))
    from workpal_backend.auth.tokens import issue_session
    token = issue_session(other_id, 'colleague@example.com', 'Colleague', settings.auth_secret, 3600)
    # A valid signed session supplies a second principal, with membership in TAP.
    with TestClient(create_app(settings)) as colleague:
        response = colleague.get(query, headers={'Authorization': 'Bearer ' + token, 'X-Workspace-Slug': 'tap'})
        assert response.json() == {}


def test_revoked_membership_cannot_write_after_workspace_resolution(content, monkeypatch):
    app, client, headers, workspace = content
    from workpal_backend.workspace_content import repository
    from workpal_backend.workspaces.models import members
    from sqlalchemy import delete
    original = repository.resolve_workspace
    def revoke_after_resolution(session, principal, slug):
        resolved = original(session, principal, slug)
        with app.state.database.transaction() as concurrent:
            concurrent.execute(delete(members).where(members.c.workspace_id == workspace['id']))
        return resolved
    monkeypatch.setattr(repository, 'resolve_workspace', revoke_after_resolution)
    response = client.post('/api/projects', headers=headers, json={'title': 'Must not persist'})
    assert response.status_code == 404
    from workpal_backend.workspace_content.models import records
    with app.state.database.transaction() as session:
        assert session.execute(select(records.c.id).where(records.c.workspace_id == workspace['id'])).first() is None


def test_bootstrap_contains_native_user_payload(content):
    _, client, headers, workspace = content
    body = client.get('/api/bootstrap', headers=headers).json()
    assert body['user'] == client.get('/api/me', headers=headers).json()
    assert body['workspace']['id'] == workspace['id']
    assert body['projects'] == []



def test_frontend_explicit_workspace_id_and_autopilot_list(content):
    app, client, headers, workspace = content
    scoped = {key: value for key, value in headers.items() if key != 'X-Workspace-Slug'}
    scoped.update({'X-Workspace-Slug': '', 'X-Workspace-ID': workspace['id']})
    assert client.get('/api/chat/sessions', headers=scoped).status_code == 200
    assert client.get('/api/chat/sessions', headers=scoped | {'X-Workspace-ID': str(uuid4())}).status_code == 404
    assert client.get('/api/autopilots', headers=headers).json() == {'autopilots': [], 'total': 0}


def test_remaining_read_contracts(content):
    app, client, headers, workspace = content
    for path, expected in [('/api/inbox/unread-summary', []), ('/api/inbox/snoozed', []), ('/api/properties', {'properties': []})]:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json() == expected
    for path in ('/api/working-agents', '/api/agent-activity-30d', '/api/search-index/manifest'):
        assert client.get(path, headers=headers).status_code == 501


def test_ordinary_comment_and_identifier_regression(content, settings):
    app, client, headers, workspace = content
    issue = client.post('/api/issues', headers=headers, json={'title': 'Persistent comment'}).json()
    path = '/api/issues/' + issue['id'] + '/comments'
    response = client.post(path, headers=headers, json={'content': 'literal <script> text'})
    assert response.status_code == 200, response.text
    comment = response.json()
    assert comment['issue_id'] == issue['id']
    for extra in ({'type': 'agent'}, {'attachment_ids': ['x']}, {'parent_id': 'x'}, {'unknown_field': True}):
        assert client.post(path, headers=headers, json={'content': 'unsupported', **extra}).status_code == 501
    assert client.post(path, headers={'X-Workspace-Slug': 'tap'}, json={'content': 'csrf'}).status_code == 403
    with TestClient(create_app(settings)) as reopened:
        assert reopened.get(path, headers=headers).json() == [comment]
        assert reopened.get('/api/issues/' + issue['identifier'], headers=headers).json()['id'] == issue['id']
    other = client.post('/api/workspaces', headers=headers, json={'name': 'Other', 'slug': 'other', 'issue_prefix': 'OTH'}).json()
    foreign = headers | {'X-Workspace-Slug': other['slug']}
    assert client.get('/api/issues/' + issue['identifier'], headers=foreign).status_code == 404
    assert client.post(path, headers=foreign, json={'content': 'foreign'}).status_code == 404
