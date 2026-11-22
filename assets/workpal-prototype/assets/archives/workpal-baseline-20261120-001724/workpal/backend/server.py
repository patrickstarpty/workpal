"""Workpal loopback-only HTTP service. Python 3.10+, standard library only."""
import argparse
import json
import mimetypes
from pathlib import Path
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 16 * 1024 * 1024


def database(path):
    db = sqlite3.connect(path, timeout=10)
    db.execute('PRAGMA busy_timeout=10000')
    return db


def make_server(path, port=4173):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with database(path) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, value TEXT NOT NULL, revision INTEGER NOT NULL)')
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, data, content_type='application/json; charset=utf-8'):
            body = json.dumps(data).encode() if content_type.startswith('application/json') else data
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def dispatch(self):
            host = self.headers.get('Host', '')
            if host not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}:
                return self.reply(403, {'error': 'Invalid host'})
            route = unquote(urlsplit(self.path).path)
            if route == '/api/health' and self.command == 'GET':
                with database(path) as db:
                    db.execute('SELECT 1')
                return self.reply(200, {'status': 'ok', 'storage': 'sqlite'})
            if route.startswith('/api/'):
                if self.headers.get('X-Workpal-Token') != token:
                    return self.reply(403, {'error': 'Open Workpal from this server to access its data.'})
                if route == '/api/records' and self.command == 'GET':
                    with database(path) as db:
                        keys = [row[0] for row in db.execute('SELECT key FROM records ORDER BY key')]
                    return self.reply(200, {'keys': keys})
                if not route.startswith('/api/records/'):
                    return self.reply(404, {'error': 'Not found'})
                key = route[len('/api/records/'):]
                if not key.startswith('workpal.') or len(key) > 240 or '/' in key:
                    return self.reply(400, {'error': 'Invalid record key'})
                if self.command == 'GET':
                    with database(path) as db:
                        row = db.execute('SELECT value, revision FROM records WHERE key=?', (key,)).fetchone()
                    return self.reply(200, {'value': row[0] if row else None, 'revision': row[1] if row else 0})
                if self.command != 'PUT':
                    return self.reply(405, {'error': 'Method not allowed'})
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= MAX_BODY:
                        return self.reply(413, {'error': 'Record must be between 1 byte and 16 MiB'})
                    if self.headers.get_content_type() != 'application/json':
                        return self.reply(415, {'error': 'JSON required'})
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict) or not isinstance(payload.get('value'), str) or type(payload.get('revision')) is not int or payload['revision'] < 0:
                        raise ValueError('Invalid value or revision')
                except (ValueError, UnicodeError):
                    return self.reply(400, {'error': 'Expected a string value and a nonnegative integer revision'})
                with database(path) as db:
                    db.execute('BEGIN IMMEDIATE')
                    row = db.execute('SELECT revision FROM records WHERE key=?', (key,)).fetchone()
                    revision = row[0] if row else 0
                    if revision != payload['revision']:
                        return self.reply(409, {'error': 'This record changed in another tab. Reload before saving.'})
                    revision += 1
                    db.execute('INSERT INTO records VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, revision=excluded.revision', (key, payload['value'], revision))
                return self.reply(200, {'revision': revision})
            if self.command != 'GET':
                return self.reply(405, {'error': 'Method not allowed'})
            if route == '/':
                html = (ROOT / 'index.html').read_text()
                config = '<script>globalThis.WorkpalBackend=' + json.dumps({'token': token}) + ';</script><script src="/src/backend-storage.js"></script>'
                return self.reply(200, html.replace('<script src="src/brand.js">', config + '<script src="src/brand.js">').encode(), 'text/html; charset=utf-8')
            # Only publish product assets, never source credentials or database files.
            file = (ROOT / route.lstrip('/')).resolve()
            allowed = any(file.is_relative_to(ROOT / folder) for folder in ('src', 'assets'))
            if not allowed or not file.is_file() or file.suffix not in {'.js', '.css', '.svg', '.png', '.jpg', '.woff2', '.ttf'}:
                return self.reply(404, {'error': 'Not found'})
            return self.reply(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or 'application/octet-stream')

        def handle_request(self):
            try:
                self.dispatch()
            except (sqlite3.Error, OSError):
                self.reply(503, {'error': 'Storage is unavailable. Your changes have not been saved.'})

        do_GET = do_PUT = do_POST = do_DELETE = do_PATCH = handle_request

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4173)
    parser.add_argument('--db', type=Path, default=ROOT / 'data' / 'workpal.sqlite3')
    args = parser.parse_args()
    server = make_server(args.db, args.port)
    print(f'Workpal: http://127.0.0.1:{server.server_port}\nSQLite: {args.db.resolve()}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
