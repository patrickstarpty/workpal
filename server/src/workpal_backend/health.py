"""Health responses derived from cmd/server/health.go.

SQLite migration-history equivalence remains separately unverified.
"""
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
import os

from fastapi.responses import JSONResponse, Response
from sqlalchemy import text


def wire_response(body, status=200):
    payload = JSONResponse(body).body + b'\n'
    return Response(payload, status_code=status, media_type='application/json')


class ServerHealth:
    def __init__(self):
        self.started_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        self.pid = os.getpid()
        self.cache_ttl = 3.0
        self._cached = None
        self._lock = Lock()

    def live(self):
        return wire_response(dict(status='ok', pid=self.pid, commit='unknown', started_at=self.started_at))

    def ready(self, database):
        with self._lock:
            now = monotonic()
            if self.cache_ttl > 0 and self._cached is not None:
                expires, body, status = self._cached
                if now < expires:
                    return wire_response(body, status)
            body, status = self._compute(database)
            self._cached = (now + self.cache_ttl, body, status)
            return wire_response(body, status)

    @staticmethod
    def _compute(database):
        checks = dict(db='ok', migrations='ok')
        try:
            if database is None:
                raise RuntimeError('database unavailable')
            with database.engine.connect() as connection:
                connection.execute(text('SELECT 1'))
        except Exception:
            checks.update(db='error', migrations='unknown')
            return dict(status='not_ready', checks=checks), 503
        try:
            checks['migrations'] = database.readiness()
        except Exception:
            checks['migrations'] = 'error'
        ok = checks['migrations'] == 'ok'
        return dict(status='ok' if ok else 'not_ready', checks=checks), 200 if ok else 503
