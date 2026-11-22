"""Source-derived request cases from handler/workspace.go; not dual-run evidence."""
import pytest
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


@pytest.fixture
def workspace_client(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        token = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        client.headers['Authorization'] = 'Bearer ' + token
        yield client, app


def test_create_preserves_optional_fields_and_go_decoding(workspace_client):
    client, app = workspace_client
    response = client.post('/api/workspaces', content='{"NAME":" A ","SLUG":" decode-case ","description":" raw ","context":"context"} trailing')
    assert response.status_code == 201
    workspace = response.json()
    assert workspace['name'] == 'A'
    assert workspace['description'] == ' raw '
    assert workspace['context'] == 'context'
    assert client.get('/api/workspaces/' + workspace['id']).json() == workspace


@pytest.mark.parametrize('body,error', [
    ('null', 'name and slug are required'),
    ('{}', 'name and slug are required'),
    ('{"name":null,"slug":"valid"}', 'name and slug are required'),
    ('{"name":2,"name":"A","slug":"valid"}', 'invalid request body'),
    ('{"name":"A","slug":"bad_slug"}', 'slug must contain only lowercase letters, numbers, and hyphens'),
    ('{"name":"A","slug":"admin"}', 'slug is reserved'),
    ('{"name":"A","slug":"valid","issue_prefix":"!"}', 'issue prefix must be 1-10 uppercase letters or digits'),
    ('{"name":"A","slug":"valid","description":7}', 'invalid request body'),
])
def test_create_errors(workspace_client, body, error):
    client, _ = workspace_client
    response = client.post('/api/workspaces', content=body)
    assert response.status_code == 400
    assert response.json() == {'error': error}
    assert client.get('/api/workspaces').json() == []


def test_disabled_creation_precedes_decode(workspace_client):
    client, app = workspace_client
    app.state.settings.disable_workspace_creation = True
    response = client.post('/api/workspaces', content='{')
    assert response.status_code == 403
    assert response.json() == {'error':'workspace creation is disabled for this instance'}


def test_duplicate_null_string_retains_go_value(workspace_client):
    client, _ = workspace_client
    response = client.post('/api/workspaces', content='{"name":"A","name":null,"slug":"dup-null"}')
    assert response.status_code == 201
    assert response.json()['name'] == 'A'


def test_update_null_case_and_trailing_value(workspace_client):
    client, _ = workspace_client
    workspace = client.post('/api/workspaces', json={'name':'A','slug':'patch-decode'}).json()
    url = '/api/workspaces/' + workspace['id']
    response = client.put(url, content='null')
    assert response.status_code == 200
    response = client.put(url, content='{"NAME":"B","CONTEXT":" updated "}{}')
    assert response.status_code == 200
    assert response.json()['name'] == 'B'
    assert response.json()['context'] == ' updated '
    response = client.put(url, content='{"name":3,"name":"B"}')
    assert response.status_code == 400
    assert response.json() == {'error':'invalid request body'}


def test_pin_case_and_trailing_value(workspace_client):
    client, _ = workspace_client
    workspace = client.post('/api/workspaces', json={'name':'A','slug':'pin-decode'}).json()
    url = '/api/workspaces/' + workspace['id'] + '/pin'
    assert client.put(url, content='{"PINNED":true} trailing').status_code == 200
    response = client.put(url, content='{"pinned":1,"pinned":true}')
    assert response.status_code == 400
    assert response.json() == {'error':'pinned must be a boolean'}


def test_create_go_unicode_case_and_whitespace(workspace_client):
    client, _ = workspace_client
    response = client.post('/api/workspaces', json={'name':'\u001cA\u001c','slug':'\u0130-slug'})
    assert response.status_code == 201
    assert response.json()['slug'] == 'i-slug'
    assert response.json()['name'] == '\u001cA\u001c'
    response = client.post('/api/workspaces', json={'name':'A','slug':'sharp-s','issue_prefix':'\u00df'})
    assert response.status_code == 400


@pytest.mark.parametrize('table,error', [('workspaces','failed to create workspace'), ('members','failed to add owner'), ('issue_status','failed to seed issue statuses')])
def test_create_database_failures_rollback(workspace_client, table, error):
    from sqlalchemy import event, select, func
    from sqlalchemy.exc import OperationalError
    from workpal_backend.workspaces.models import workspaces, members, issue_status
    client, app = workspace_client
    def fail(connection, cursor, statement, parameters, context, many):
        if statement.startswith('INSERT INTO ' + table + ' '):
            raise OperationalError(statement, parameters, RuntimeError('injected database failure'))
    engine = app.state.database.engine
    event.listen(engine, 'before_cursor_execute', fail)
    try:
        response = client.post('/api/workspaces', json={'name':'A','slug':'rollback-case'})
        assert response.status_code == 500
        assert response.json() == {'error':error}
    finally:
        event.remove(engine, 'before_cursor_execute', fail)
    with app.state.database.transaction() as session:
        for model in (workspaces, members, issue_status):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_update_authorization_precedes_body_decode(workspace_client):
    from uuid import uuid4
    from sqlalchemy import update
    from workpal_backend.workspaces.models import members
    client, app = workspace_client
    response = client.put('/api/workspaces/' + str(uuid4()), content='{')
    assert response.status_code == 404
    assert response.json() == {'error':'workspace not found'}
    workspace = client.post('/api/workspaces', json={'name':'A','slug':'role-before-body'}).json()
    with app.state.database.transaction() as session:
        session.execute(update(members).where(members.c.workspace_id == workspace['id']).values(role='member'))
    response = client.put('/api/workspaces/' + workspace['id'], content='{')
    assert response.status_code == 403
    assert response.json() == {'error':'insufficient permissions'}
