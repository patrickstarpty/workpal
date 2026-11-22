import signal
import pytest
from sqlalchemy import select
from workpal_backend import worker
from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.files.storage import LocalBlobStore
from workpal_backend.files.repository import reserve_intent
from workpal_backend.files.models import upload_intent
from workpal_backend.files.reconcile import reconcile_expired


def test_constructor_failure_restores_signal_handlers(settings, monkeypatch):
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    def unavailable(_):
        raise OSError('database startup failed')
    monkeypatch.setattr(worker, 'Database', unavailable)
    try:
        with pytest.raises(OSError, match='startup failed'):
            worker.run(settings)
        assert all(signal.getsignal(sig) == handler for sig, handler in previous.items())
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def test_stop_between_cleanup_items_preserves_reclaimable_work(settings, tmp_path):
    migrate(settings)
    root = tmp_path/'blobs'
    root.mkdir()
    store = LocalBlobStore(root)
    db = Database(settings)
    try:
        with db.transaction() as session:
            rows = [reserve_intent(session, {'owner_id': 'owner'}, {}, store.new_key(), now=1) for _ in range(2)]
        for row in rows:
            with store.create_staging(row['storage_key'], row['staging_key']) as stream:
                stream.write(b'pending')
        def stop_after_one():
            return len(list(root.iterdir())) < 2
        result = reconcile_expired(db, store, now=100, should_stop=stop_after_one)
        assert result['completed'] == 1
        assert len(list(root.iterdir())) == 1
        with db.transaction() as session:
            remaining = session.execute(select(upload_intent)).mappings().all()
            assert len(remaining) == 1
            assert remaining[0]['state'] == 'deleting'
            assert remaining[0]['lease_expires_at'] > 100
        assert reconcile_expired(db, store, now=200)['completed'] == 1
        assert list(root.iterdir()) == []
    finally:
        db.close()
