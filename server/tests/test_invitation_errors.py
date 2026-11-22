import sqlite3
import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate

@pytest.mark.parametrize('busy,status,body', [(False,500,{'error':'failed to list invitations'}),(True,503,None)])
def test_list_database_error(settings, busy, status, body):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        token = client.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        def fail(conn,cursor,statement,parameters,context,executemany):
            if 'FROM workspace_invitation' in statement:
                raise OperationalError(statement,parameters,sqlite3.OperationalError('database is locked' if busy else 'disk I/O error'))
        event.listen(app.state.database.engine,'before_cursor_execute',fail)
        try:
            response = client.get('/api/invitations',headers={'Authorization':'Bearer '+token})
            assert response.status_code == status
            if body: assert response.json() == body
        finally:
            event.remove(app.state.database.engine,'before_cursor_execute',fail)

from test_workspace_invitations import context


@pytest.mark.parametrize('busy,status', [(False,500),(True,503)])
def test_revoke_sql_failure_preserves_invitation_and_events(context, settings, busy, status):
    from sqlalchemy import select
    from workpal_backend.workspaces import invitations
    from workpal_backend.infrastructure.outbox import outbox
    from workpal_backend.auth.tokens import issue_session
    db, actor, target, stranger, wid = context
    with db.transaction() as session:
        invitation = invitations.create_invitation(session, actor, wid, 'target@example.com')
        before = list(session.execute(select(outbox)).mappings())
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    app = create_app(settings)
    with TestClient(app) as client:
        token = issue_session(actor['user_id'], 'dev@workpal.local', 'Owner', settings.auth_secret, 3600)
        def fail(conn,cursor,statement,parameters,ctx,executemany):
            if statement.startswith('DELETE FROM workspace_invitation'):
                raise OperationalError(statement,parameters,sqlite3.OperationalError('database is locked' if busy else 'disk I/O error'))
        event.listen(app.state.database.engine,'before_cursor_execute',fail)
        try:
            response = client.delete(f"/api/workspaces/{wid}/invitations/{invitation['id']}",headers={'Authorization':'Bearer '+token})
            assert response.status_code == status
            if busy:
                assert response.json()['retryable'] is True
                assert response.headers['retry-after'] == '1'
            else:
                assert response.json() == {'error':'failed to revoke invitation'}
        finally:
            event.remove(app.state.database.engine,'before_cursor_execute',fail)
    with db.transaction() as session:
        assert dict(invitations.lookup(session, invitation['id'])) == invitation
        assert list(session.execute(select(outbox)).mappings()) == before
