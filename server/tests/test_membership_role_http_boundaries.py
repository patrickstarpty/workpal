import pytest
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


@pytest.mark.parametrize('body,status,error', [
    ('{"role":"admin","ROLE":"owner"}', 200, None),
    ('{"role":"owner","role":null}', 200, None),
    ('{"ROLE":"admin","role":"owner"} trailing', 200, None),
    ('{"role":1,"role":"owner"}', 400, 'invalid request body'),
    ('[]', 400, 'invalid request body'),
    ('null', 400, 'role is required'),
    ('{"unknown":true}', 400, 'role is required'),
    ('{"role":""}', 400, 'role is required'),
    ('{"role":"OWNER"}', 400, 'invalid member role'),
])
def test_ordered_go_decode(settings, body, status, error):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        token = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        headers = {'Authorization':'Bearer '+token}
        ws = client.post('/api/workspaces', json={'name':'A','slug':'alpha'}, headers=headers).json()
        base = '/api/workspaces/'+ws['id']+'/members'
        member = client.get(base, headers=headers).json()[0]
        response = client.patch(base+'/'+member['id'], content=body, headers=headers)
        assert response.status_code == status
        if error:
            assert response.json()['error'] == error
