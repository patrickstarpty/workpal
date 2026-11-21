"""Dashboard contracts against authenticated routes and a temporary SQLite DB."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


@pytest.fixture
def dashboard(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        token = client.post('/auth/verify-code', json={
            'email': 'dev@workpal.local', 'code': '888888',
        }).json()['token']
        authorization = {'Authorization': 'Bearer ' + token}
        workspace = client.post('/api/workspaces', headers=authorization,
                                json={'name': 'Analytics', 'slug': 'analytics'}).json()
        headers = dict(authorization, **{'X-Workspace-Slug': workspace['slug']})
        yield client, app, workspace, headers


def test_empty_dashboard_uses_no_generated_runs(dashboard):
    client, _, _, headers = dashboard
    for route in ('usage/daily', 'usage/by-agent', 'agent-runtime', 'runtime/daily',
                  'failures/daily', 'failures/by-agent'):
        response = client.get('/api/dashboard/' + route, headers=headers)
        assert response.status_code == 200
        assert response.json() == []
    contribution = client.get('/api/dashboard/contribution?days=1', headers=headers)
    assert contribution.status_code == 200
    assert contribution.json()['totals'] == {
        'commits': 0, 'tickets': 0, 'added': 0, 'deleted': 0,
        'agentLines': 0, 'humanLines': 0,
    }
    assert contribution.json()['rows'] == []


def save_records(app, workspace_id, kind, bodies):
    from workpal_backend.workspace_content.models import records
    with app.state.database.transaction() as session:
        for position, body in enumerate(bodies):
            session.execute(records.insert().values(
                workspace_id=workspace_id, kind=kind, id=body['id'],
                body=body, position=position,
            ))


@pytest.fixture
def recorded_dashboard(dashboard, monkeypatch):
    from workpal_backend.workspace_content import analytics
    monkeypatch.setattr(analytics, 'utc_now', lambda: datetime(2026, 11, 21, 1, tzinfo=timezone.utc))
    client, app, workspace, headers = dashboard
    save_records(app, workspace['id'], 'projects', [{'id': 'p1'}, {'id': 'p2'}])
    save_records(app, workspace['id'], 'issues', [
        {'id': 'i1', 'identifier': 'A-1', 'title': 'First', 'project_id': 'p1',
         'parent_issue_id': 'parent'},
        {'id': 'i2', 'identifier': 'B-2', 'title': 'Second', 'project_id': 'p2'},
        {'id': 'parent', 'identifier': 'A-3', 'title': 'Parent', 'project_id': 'p1',
         'assignee_type': 'squad', 'assignee_id': 'Review squad'},
        {'id': 'orphan', 'identifier': 'C-4', 'title': 'Orphan', 'project_id': 'deleted'},
    ])
    first = {
        'id': 'r1', 'project_id': 'p1', 'issue_id': 'i1', 'agent_id': 'a1',
        'completed_at': '2026-11-20T23:30:00Z', 'provider': 'openai', 'model': 'm1',
        'input_tokens': 10, 'output_tokens': 2, 'cache_read_tokens': 3,
        'cache_write_tokens': 4, 'total_seconds': 100, 'task_count': 1,
        'failed_count': 0, 'cancelled_count': 0, 'failure_reason': '',
    }
    save_records(app, workspace['id'], 'analytics_runs', [
        first,
        dict(first, id='r2', completed_at='2026-11-21T00:30:00Z', input_tokens=20,
             output_tokens=4, cache_read_tokens=6, cache_write_tokens=8,
             total_seconds=200, failed_count=1, failure_reason='timeout'),
        dict(first, id='r3', project_id='p2', issue_id='i2', agent_id='a2',
             provider='anthropic', model='m2', completed_at='2026-11-20T22:00:00Z',
             input_tokens=30, output_tokens=6, cache_read_tokens=9,
             cache_write_tokens=12, total_seconds=300, cancelled_count=1),
        dict(first, id='old', completed_at='2026-11-19T05:00:00Z'),
        dict(first, id='future', completed_at='2026-11-22T05:00:00Z'),
        dict(first, id='deleted-issue', issue_id='missing'),
        dict(first, id='deleted-project', project_id='deleted'),
    ])
    return dashboard


def test_dashboard_rollups_preserve_dimensions_and_exclude_deleted_records(recorded_dashboard):
    client, _, _, headers = recorded_dashboard
    def get(route):
        response = client.get('/api/dashboard/' + route, headers=headers,
                              params={'days': 1, 'tz': 'Asia/Shanghai'})
        assert response.status_code == 200
        return response.json()
    assert get('usage/daily') == [
        {'date': '2026-11-21', 'provider': 'openai', 'model': 'm1', 'input_tokens': 30,
         'output_tokens': 6, 'cache_read_tokens': 9, 'cache_write_tokens': 12, 'task_count': 2},
        {'date': '2026-11-21', 'provider': 'anthropic', 'model': 'm2', 'input_tokens': 30,
         'output_tokens': 6, 'cache_read_tokens': 9, 'cache_write_tokens': 12, 'task_count': 1},
    ]
    assert get('usage/by-agent') == [
        {'agent_id': 'a1', 'provider': 'openai', 'model': 'm1', 'input_tokens': 30,
         'output_tokens': 6, 'cache_read_tokens': 9, 'cache_write_tokens': 12, 'task_count': 2},
        {'agent_id': 'a2', 'provider': 'anthropic', 'model': 'm2', 'input_tokens': 30,
         'output_tokens': 6, 'cache_read_tokens': 9, 'cache_write_tokens': 12, 'task_count': 1},
    ]
    assert get('runtime/daily') == [
        {'date': '2026-11-21', 'total_seconds': 600, 'task_count': 3, 'failed_count': 1, 'cancelled_count': 1},
    ]
    assert get('agent-runtime') == [
        {'agent_id': 'a1', 'total_seconds': 300, 'task_count': 2, 'failed_count': 1, 'cancelled_count': 0},
        {'agent_id': 'a2', 'total_seconds': 300, 'task_count': 1, 'failed_count': 0, 'cancelled_count': 1},
    ]
    assert get('failures/daily') == [
        {'date': '2026-11-21', 'failure_reason': '', 'task_count': 2},
        {'date': '2026-11-21', 'failure_reason': 'timeout', 'task_count': 1},
    ]
    assert get('failures/by-agent') == [
        {'agent_id': 'a1', 'failure_reason': '', 'task_count': 1},
        {'agent_id': 'a1', 'failure_reason': 'timeout', 'task_count': 1},
        {'agent_id': 'a2', 'failure_reason': '', 'task_count': 1},
    ]


def test_dashboard_filters_calendar_days_timezone_and_project(recorded_dashboard):
    client, _, _, headers = recorded_dashboard
    route = '/api/dashboard/runtime/daily'
    assert client.get(route, headers=headers, params={'days': 1, 'tz': 'UTC'}).json() == [
        {'date': '2026-11-21', 'total_seconds': 200, 'task_count': 1, 'failed_count': 1, 'cancelled_count': 0},
    ]
    assert client.get(route, headers=headers, params={
        'days': 1, 'tz': 'Asia/Shanghai', 'project_id': 'p1',
    }).json() == [
        {'date': '2026-11-21', 'total_seconds': 300, 'task_count': 2, 'failed_count': 1, 'cancelled_count': 0},
    ]
    assert client.get(route, headers=headers, params={'project_id': 'missing'}).json() == []
    assert client.get(route, headers=headers, params={'days': 3, 'tz': 'UTC'}).json()[0] == {
        'date': '2026-11-19', 'total_seconds': 100, 'task_count': 1, 'failed_count': 0, 'cancelled_count': 0,
    }


@pytest.mark.parametrize('query', [
    'days=invalid', 'days=0', 'days=-1', 'days=1.5', 'days=366', 'days=NaN',
    'tz=Does/NotExist', 'project_id=abc%00def',
])
def test_invalid_dashboard_filters_are_explicit_errors(dashboard, query):
    client, _, _, headers = dashboard
    for route in ('usage/daily', 'contribution'):
        response = client.get('/api/dashboard/' + route + '?' + query, headers=headers)
        assert response.status_code == 400
        assert isinstance(response.json()['error'], str)


COMMIT = {
    'repository': 'local/repo', 'sha': 'a',
    'message': 'A-1 B-2 A-1\nCo-authored-by: Workpal <workpal@users.noreply.github.com>',
    'at': '2026-11-21T07:30:00+08:00', 'additions': 80, 'deletions': 20,
    'agentLines': 40, 'humanLines': 20,
}


def test_contribution_attribution_deduplication_and_squad_inheritance(recorded_dashboard):
    client, _, _, headers = recorded_dashboard
    commits = [
        COMMIT, COMMIT,
        dict(COMMIT, sha='b', message='A-1', agentLines=0, humanLines=100),
        dict(COMMIT, sha='excluded', message='Unknown ticket C-4'),
        dict(COMMIT, sha='future', at='2026-11-21T02:00:00Z'),
        dict(COMMIT, sha='old', at='2026-11-18T00:00:00Z'),
    ]
    route = '/api/dashboard/contribution'
    assert client.put(route, headers=headers, json={'commits': commits}).json() == {'count': 6}
    response = client.get(route, headers=headers, params={'days': 1, 'tz': 'Asia/Shanghai'})
    assert response.status_code == 200
    assert response.json() == {
        'totals': {'commits': 2, 'tickets': 2, 'added': 160, 'deleted': 40,
                   'agentLines': 80, 'humanLines': 120},
        'daily': [{'date': '2026-11-21', 'commits': 2, 'agentLines': 80, 'humanLines': 120}],
        'rows': [
            {'id': 'i1', 'identifier': 'A-1', 'title': 'First', 'team': 'Review squad',
             'commits': 2, 'added': 160, 'deleted': 40, 'agentLines': 80, 'humanLines': 120},
            {'id': 'i2', 'identifier': 'B-2', 'title': 'Second', 'team': 'Unassigned',
             'commits': 1, 'added': 80, 'deleted': 20, 'agentLines': 80, 'humanLines': 20},
        ],
        'excluded': 1,
    }
    project = client.get(route, headers=headers, params={
        'days': 1, 'tz': 'Asia/Shanghai', 'project_id': 'p2',
    }).json()
    assert project['totals'] == {'commits': 1, 'tickets': 1, 'added': 80, 'deleted': 20,
                                 'agentLines': 80, 'humanLines': 20}
    assert project['excluded'] == 2
    assert client.get(route, headers=headers, params={'days': 1, 'tz': 'UTC'}).json()['totals']['commits'] == 0


@pytest.mark.parametrize('invalid', [
    None, {}, [None], [dict(COMMIT, repository=' ')], [dict(COMMIT, sha='')],
    [dict(COMMIT, message=None)], [dict(COMMIT, at='invalid')],
    [dict(COMMIT, additions=True)], [dict(COMMIT, additions=-1)],
    [dict(COMMIT, deletions=0.5)], [dict(COMMIT, additions=2 ** 53)],
    [dict(COMMIT, additions=2 ** 53 - 1, deletions=1)],
    [dict(COMMIT, agentLines=81)], [dict(COMMIT, agentLines=True)],
    [{key: value for key, value in COMMIT.items() if key != 'humanLines'}],
])
def test_invalid_contribution_import_keeps_stored_commits(recorded_dashboard, invalid):
    client, _, _, headers = recorded_dashboard
    route = '/api/dashboard/contribution'
    assert client.put(route, headers=headers, json={'commits': [COMMIT]}).status_code == 200
    before = client.get(route, headers=headers).json()
    response = client.put(route, headers=headers, json={'commits': invalid})
    assert response.status_code == 400
    assert isinstance(response.json()['error'], str)
    assert client.get(route, headers=headers).json() == before


def test_contribution_import_preserves_timestamps_and_survives_restart(recorded_dashboard):
    client, app, workspace, headers = recorded_dashboard
    route = '/api/dashboard/contribution'
    assert client.put(route, headers=headers, json={'commits': [dict(COMMIT, additions=80.0, extra='discard')]}).json() == {'count': 1}
    from sqlalchemy import select
    from workpal_backend.workspace_content.models import records
    with app.state.database.transaction() as session:
        stored = session.scalar(select(records.c.body).where(
            records.c.workspace_id == workspace['id'], records.c.kind == 'contribution_data',
            records.c.id == 'workspace',
        ))
    assert stored['commits'] == [COMMIT]
    with TestClient(create_app(app.state.settings)) as restarted:
        assert restarted.get(route, headers=headers).json()['totals']['commits'] == 1
        assert restarted.put(route, headers=headers, json={'commits': []}).json() == {'count': 0}
        assert restarted.get(route, headers=headers).json()['totals']['commits'] == 0


def test_contribution_attribution_fallback_and_cyclic_ancestors(recorded_dashboard):
    client, app, workspace, headers = recorded_dashboard
    save_records(app, workspace['id'], 'issues', [
        {'id': 'cycle-a', 'identifier': 'C-5', 'title': 'Cycle', 'project_id': 'p1', 'parent_issue_id': 'cycle-b'},
        {'id': 'cycle-b', 'identifier': 'C-6', 'title': 'Cycle parent', 'project_id': 'p1', 'parent_issue_id': 'cycle-a'},
    ])
    plain = {key: value for key, value in COMMIT.items() if key not in ('agentLines', 'humanLines')}
    commits = [
        dict(plain, sha='plain', message='C-5', additions=10, deletions=0),
        dict(plain, sha='assisted', message='C-5\nCo-authored-by: Workpal <workpal@users.noreply.github.com>', additions=10, deletions=0),
        dict(plain, sha='other-author', message='C-5\nCo-authored-by: Other <other@example.com>', additions=10, deletions=0),
        dict(COMMIT, sha='partial', message='C-5'),
    ]
    route = '/api/dashboard/contribution'
    assert client.put(route, headers=headers, json={'commits': commits}).status_code == 200
    result = client.get(route, headers=headers).json()
    assert result['totals'] == {'commits': 4, 'tickets': 1, 'added': 110, 'deleted': 20,
                                'agentLines': 50, 'humanLines': 80}
    assert result['rows'][0]['team'] == 'Unassigned'


def test_contribution_write_failure_rolls_back_database(recorded_dashboard, monkeypatch):
    from workpal_backend.workspace_content import analytics_routes
    client, _, _, headers = recorded_dashboard
    route = '/api/dashboard/contribution'
    assert client.put(route, headers=headers, json={'commits': [COMMIT]}).status_code == 200
    before = client.get(route, headers=headers).json()
    original = analytics_routes.put_record
    def fail_after_write(*args):
        original(*args)
        raise RuntimeError('injected persistence failure')
    monkeypatch.setattr(analytics_routes, 'put_record', fail_after_write)
    with pytest.raises(RuntimeError, match='injected persistence failure'):
        client.put(route, headers=headers, json={'commits': []})
    assert client.get(route, headers=headers).json() == before


@pytest.mark.parametrize('body', ['null', '[]', '{', '{"commits":NaN}', '{}'])
def test_contribution_rejects_invalid_json_body(dashboard, body):
    client, _, _, headers = dashboard
    response = client.put('/api/dashboard/contribution', headers=headers, content=body)
    assert response.status_code == 400


def test_contribution_enforces_batch_limit_and_cookie_csrf(dashboard):
    client, _, _, headers = dashboard
    route = '/api/dashboard/contribution'
    assert client.put(route, headers=headers, json={'commits': [COMMIT] * 20_001}).status_code == 400
    cookie_headers = {'X-Workspace-Slug': 'analytics'}
    assert client.put(route, headers=cookie_headers, json={'commits': []}).status_code == 403
    cookie_headers['X-CSRF-Token'] = client.cookies['workpal_csrf_session']
    assert client.put(route, headers=cookie_headers, json={'commits': []}).status_code == 200


def test_dashboard_authentication_and_workspace_isolation(recorded_dashboard):
    from sqlalchemy import select, func
    from workpal_backend.auth.models import users
    from workpal_backend.workspaces import service
    from workpal_backend.workspace_content.models import records
    client, app, workspace, headers = recorded_dashboard
    route = '/api/dashboard/contribution'
    assert client.put(route, headers=headers, json={'commits': [COMMIT]}).status_code == 200
    second = client.post('/api/workspaces', headers=headers,
                         json={'name': 'Second', 'slug': 'second'}).json()
    second_headers = dict(headers, **{'X-Workspace-Slug': second['slug']})
    save_records(app, second['id'], 'projects', [{'id': 'p1'}])
    save_records(app, second['id'], 'issues', [{'id': 'i1', 'project_id': 'p1', 'identifier': 'A-1', 'title': 'Private'}])
    assert client.get('/api/dashboard/usage/daily', headers=second_headers).json() == []
    assert client.get(route, headers=second_headers).json()['totals']['commits'] == 0
    assert client.put(route, headers=second_headers, json={'commits': []}).status_code == 200
    assert client.get(route, headers=headers).json()['totals']['commits'] == 1
    with app.state.database.transaction() as session:
        session.execute(users.insert().values(id='foreign-user', email='foreign@example.com',
                                               name='Foreign', created_at='2026-01-01', updated_at='2026-01-01'))
        foreign = service.create_workspace(session, 'foreign-user', 'Foreign', 'foreign')
        count = session.scalar(select(func.count()).select_from(records))
    for slug in ('missing', foreign['slug']):
        denied_headers = dict(headers, **{'X-Workspace-Slug': slug})
        assert client.get('/api/dashboard/usage/daily', headers=denied_headers).status_code == 404
        assert client.get(route, headers=denied_headers).status_code == 404
        assert client.put(route, headers=denied_headers, json={'commits': []}).status_code == 404
    with app.state.database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(records)) == count
    assert client.get(route, headers={'Authorization': headers['Authorization']}).status_code == 400
    client.cookies.clear()
    assert client.get(route, headers={'X-Workspace-Slug': workspace['slug']}).status_code == 401
    assert client.put(route, headers={'X-Workspace-Slug': workspace['slug']}, json={'commits': []}).status_code == 401
