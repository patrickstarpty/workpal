from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from workpal_backend.frontend import mount_frontend


def test_frontend_boundaries(tmp_path):
    (tmp_path/'index.html').write_text('<html>Workpal</html>')
    (tmp_path/'asset.js').write_text('export {}')
    app = FastAPI()
    mount_frontend(app, tmp_path)
    with TestClient(app) as client:
        for path in ('/', '/workspace/example'):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers['cache-control'] == 'no-cache'
        assert client.head('/workspace/example').status_code == 200
        assert 'javascript' in client.get('/asset.js').headers['content-type']
        for path in ('/api/missing', '/auth/missing', '/ws/missing', '/v1/missing', '/plugin-surfaces/missing', '/missing.js', '/%2e%2e/secret'):
            assert client.get(path).status_code == 404


def test_missing_build(tmp_path):
    with pytest.raises(ValueError, match='build'):
        mount_frontend(FastAPI(), tmp_path)


def test_frontend_rejects_index_symlink_outside_build(tmp_path):
    root = tmp_path / 'dist'
    root.mkdir()
    secret = tmp_path / 'secret.html'
    secret.write_text('private')
    (root / 'index.html').symlink_to(secret)
    with pytest.raises(ValueError, match='build'):
        mount_frontend(FastAPI(), root)
