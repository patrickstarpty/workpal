import json
import re
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from server import make_server


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = self.temp.name + '/workpal.sqlite3'
        self.start()

    def start(self):
        self.server = make_server(self.path, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        html = urlopen(self.base).read().decode()
        self.token = re.search(r'"token": "([^"]+)"', html)[1]

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def tearDown(self):
        self.stop()
        self.temp.cleanup()

    def request(self, path, body=None, token=True):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-Workpal-Token'] = self.token
        request = Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        if body is not None:
            request.method = 'PUT'
        try:
            response = urlopen(request)
        except HTTPError as error:
            response = error
        return response.status, json.loads(response.read())

    def test_restart_persistence_and_conflict(self):
        route = '/api/records/workpal.studio.v2'
        value = json.dumps({'notes': ['中文 <script>text only</script>']})
        self.assertEqual(self.request(route, {'value': value, 'revision': 0}), (200, {'revision': 1}))
        self.assertEqual(self.request(route, {'value': 'overwrite', 'revision': 0})[0], 409)
        self.stop()
        self.start()
        self.assertEqual(self.request(route), (200, {'value': value, 'revision': 1}))
        self.assertIn('workpal.studio.v2', self.request('/api/records')[1]['keys'])

    def test_boundaries(self):
        self.assertEqual(self.request('/api/records', token=False)[0], 403)
        for route in ['/backend/server.py', '/data/workpal.sqlite3', '/src/../backend/server.py']:
            self.assertEqual(self.request(route)[0], 404)
        self.assertEqual(self.request('/api/records/other', {'value': 'x', 'revision': 0})[0], 400)
        self.assertEqual(self.request('/api/records/workpal.test', {'value': {}, 'revision': 0})[0], 400)
        self.assertEqual(self.request('/api/records/workpal.test', {'value': 'x', 'revision': True})[0], 400)
        req = Request(self.base + '/api/health', headers={'Host': 'attacker.example'})
        with self.assertRaises(HTTPError) as error:
            urlopen(req)
        self.assertEqual(error.exception.code, 403)


if __name__ == '__main__':
    unittest.main()
