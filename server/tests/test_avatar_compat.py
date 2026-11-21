from pathlib import Path
from test_workspace_content import content
from fastapi.testclient import TestClient
from workpal_backend.app import create_app


def test_avatar_upload_persistence_and_access(content, settings, tmp_path):
    app, client, headers, workspace = content
    settings.upload_dir = tmp_path / 'uploads'
    app.state.settings.upload_dir = settings.upload_dir
    data = Path('apps/web/public/icons/icon-192.png').read_bytes()
    result = client.post('/api/upload-file', headers=headers, files={'file': ('avatar.png', data, 'image/png')})
    assert result.status_code == 201, result.text
    url = result.json()['url']
    agent = client.post('/api/agents', headers=headers, json={'name': 'Avatar agent'}).json()
    assert client.put('/api/agents/' + agent['id'], headers=headers, json={'avatar_url': url}).status_code == 200
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(url, headers=headers).content == data
        assert restarted.get('/api/agents/' + agent['id'], headers=headers).json()['avatar_url'] == url
        assert restarted.get(url).status_code == 401
    bad = client.post('/api/upload-file', headers=headers, files={'file': ('bad.png', b'<script>bad</script>', 'image/png')})
    assert bad.status_code == 415
    assert client.post('/api/upload-file', headers=headers, files={'file': ('large.png', data + b'x' * (5 * 1024 * 1024), 'image/png')}).status_code == 413
    assert client.post('/api/upload-file', headers={'X-Workspace-Slug':'tap'}, files={'file': ('avatar.png', data, 'image/png')}).status_code == 403
    assert client.post('/api/upload-file', headers=headers, data={'issue_id':'unknown'}, files={'file': ('avatar.png', data, 'image/png')}).status_code == 501
    from sqlalchemy import delete
    from workpal_backend.workspaces.models import members
    with app.state.database.transaction() as session:
        session.execute(delete(members).where(members.c.workspace_id == workspace['id']))
    assert client.get(url, headers=headers).status_code == 404
