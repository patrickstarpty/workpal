"""Exercise durable upload recovery through real CLI process lifecycles."""
from contextlib import contextmanager
import io
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from sqlalchemy import select

from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.infrastructure.jobs import jobs
from workpal_backend.files.models import upload_intent
from workpal_backend.files.repository import finalize_ready, reserve_intent
from workpal_backend.files.storage import LocalBlobStore


def wait_for(predicate, processes, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate():
        for process in processes:
            assert process.poll() is None, 'CLI process exited before acceptance'
        assert time.monotonic() < deadline, 'Timed out waiting for durable recovery'
        time.sleep(.025)


@contextmanager
def cli(command, env, log):
    with log.open('wb') as output:
        process = subprocess.Popen(
            [sys.executable, '-m', 'workpal_backend.cli', command],
            env=env, stdout=output, stderr=subprocess.STDOUT,
        )
        try:
            yield process
        finally:
            was_running = process.poll() is None
            if was_running:
                process.send_signal(signal.SIGTERM)
            try:
                code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise AssertionError(f'{command} required SIGKILL: {log.read_text()}')
            assert was_running and code in ({0} if command == 'worker' else {0, -signal.SIGTERM}), f'{command} did not shut down gracefully ({code}): {log.read_text()}'


def test_cli_scheduled_recovery(settings, tmp_path):
    migrate(settings)
    root = tmp_path / 'bytes'
    root.mkdir(mode=0o700)
    store = LocalBlobStore(root)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    env = dict(os.environ, WORKPAL_DATABASE_URL=settings.database_url,
        WORKPAL_UPLOAD_DIR=str(root), WORKPAL_HOST='127.0.0.1', WORKPAL_PORT=str(port),
        WORKPAL_ENV='development', WORKPAL_DEV_AUTH='false',
        REDIS_URL=settings.redis_url, REDIS_KEY_PREFIX=f'test:recovery:{uuid4().hex}:',
        WORKPAL_WORKER_POLL_INTERVAL='.05', WORKPAL_RECONCILE_INTERVAL='.05',
        PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
    db = Database(settings)
    payload = b'durable upload bytes\x00\xff'

    def rows():
        with db.transaction() as session:
            return {r['id']: dict(r) for r in session.execute(select(upload_intent)).mappings()}

    def api_up(process):
        def health():
            try:
                response = httpx.get(f'http://127.0.0.1:{port}/health', timeout=.3)
                return response.status_code == 200 and response.json()['pid'] == process.pid
            except httpx.TransportError:
                return False
        wait_for(health, [process])

    try:
        # First lifecycle establishes actual API and scheduler processes before a restart.
        with cli('serve', env, tmp_path / 'api-before.log') as api:
            api_up(api)
            with cli('worker', env, tmp_path / 'worker-before.log') as worker:
                def scheduler_completed_cycle():
                    with db.transaction() as session:
                        job = session.execute(select(jobs).where(jobs.c.name == 'files.reconcile')).mappings().first()
                        return job is not None and job['token'] is None and job['last_error'] is None
                wait_for(scheduler_completed_cycle, [api, worker])
            with db.transaction() as session:
                expired = reserve_intent(session, {'owner_id': 'owner'}, {}, store.new_key(), now=1)
                published = reserve_intent(session, {'owner_id': 'owner'}, {}, store.new_key(), now=1)
                live = reserve_intent(session, {'owner_id': 'owner'}, {}, store.new_key(), lease_seconds=3600)
                ready = reserve_intent(session, {'owner_id': 'owner'}, {}, store.new_key())
            for row in (expired, published, live, ready):
                with store.create_staging(row['storage_key'], row['staging_key']) as stream:
                    size, digest = store.write_bounded(stream, io.BytesIO(payload), 1024)
                if row in (published, ready):
                    store.sync_and_promote(row['storage_key'], row['staging_key'])
            with db.transaction() as session:
                finalize_ready(session, ready['id'], ready['lease_token'],
                    {'size_bytes': size, 'sha256': digest, 'filename': 'ready.bin'})
            before = rows()
            assert before[expired['id']]['state'] == before[published['id']]['state'] == 'pending'
            assert before[ready['id']]['state'] == 'ready'
        with cli('serve', env, tmp_path / 'api-after.log') as api:
            api_up(api)
            # API startup must not do scheduler work.
            assert rows() == before
            with cli('worker', env, tmp_path / 'worker-after.log') as worker:
                wait_for(lambda: expired['id'] not in rows() and published['id'] not in rows(), [api, worker])
                time.sleep(.2)  # Observe additional scheduling cycles protecting survivors.
                assert rows() == {live['id']: before[live['id']], ready['id']: before[ready['id']]}
                assert not (root / store._name(expired['storage_key'], expired['staging_key'])).exists()
                assert not (root / store._name(published['storage_key'])).exists()
                assert (root / store._name(live['storage_key'], live['staging_key'])).read_bytes() == payload
                with store.open_ready(ready['storage_key']) as stream:
                    assert stream.read() == payload
                assert set(p.name for p in root.iterdir()) == {
                    store._name(live['storage_key'], live['staging_key']), store._name(ready['storage_key'])}
    finally:
        db.close()
