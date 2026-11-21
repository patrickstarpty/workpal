import io
import pytest
from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.files import repository as r
from workpal_backend.files.reconcile import reconcile_expired
from workpal_backend.files.storage import LocalBlobStore

@pytest.fixture
def env(settings, tmp_path):
    migrate(settings)
    db = Database(settings)
    root = tmp_path / 'blobs'; root.mkdir()
    yield db, LocalBlobStore(root.resolve())
    db.close()

@pytest.mark.parametrize('published', [False, True])
def test_recovery(env, published):
    db, store = env
    with db.transaction() as s:
        row = r.reserve_intent(s, {'owner_id':'u'}, {}, store.new_key(), now=0, lease_seconds=10)
    with store.create_staging(row['storage_key'], row['staging_key']) as f:
        store.write_bounded(f, io.BytesIO(b'abc'), 10)
    if published: store.sync_and_promote(row['storage_key'], row['staging_key'])
    assert reconcile_expired(db, store, now=11)['completed'] == 1
    assert reconcile_expired(db, store, now=12)['completed'] == 0
    assert list(store.root.iterdir()) == []


def reserve(db, store):
    with db.transaction() as s:
        return r.reserve_intent(s, {'owner_id':'u'}, {}, store.new_key(), now=0, lease_seconds=10)

def test_fencing_and_claim_winner(env):
    db, store = env; row = reserve(db, store)
    with db.transaction() as s:
        claim, = r.claim_expired(s, 11)
    with db.transaction() as s:
        assert r.claim_expired(s, 11) == []
        for operation in (r.renew_lease, lambda s,i,t,**kw: r.finalize_ready(s,i,t,{},**kw)):
            with pytest.raises(r.StaleLease): operation(s, row['id'], row['lease_token'], now=12)
    with db.transaction() as s:
        replacement, = r.claim_expired(s, 72)
        with pytest.raises(r.StaleLease): r.complete_cleanup(s, claim, now=72)
        r.complete_cleanup(s, replacement, now=72)

def test_live_and_ready_preserved_and_finalize_rollback(env):
    db, store = env; row = reserve(db, store)
    assert reconcile_expired(db, store, now=5)['claimed'] == 0
    with pytest.raises(RuntimeError):
        with db.transaction() as s:
            r.finalize_ready(s, row['id'], row['lease_token'], {'filename':'x'}, now=5)
            raise RuntimeError('rollback')
    with db.transaction() as s:
        r.finalize_ready(s, row['id'], row['lease_token'], {'filename':'x'}, now=6)
    assert reconcile_expired(db, store, now=100)['claimed'] == 0

def test_retry_outside_transaction(env, monkeypatch):
    from sqlalchemy import event
    db, store = env; row = reserve(db, store)
    active = set()
    event.listen(db.engine, 'begin', lambda c: active.add(c))
    event.listen(db.engine, 'commit', lambda c: active.discard(c))
    event.listen(db.engine, 'rollback', lambda c: active.discard(c))
    original = store.delete_owned
    def fail(*a, **kw):
        assert not active
        raise OSError('unlink failed')
    monkeypatch.setattr(store, 'delete_owned', fail)
    assert reconcile_expired(db, store, now=11)['failed'] == 1
    assert reconcile_expired(db, store, now=12)['claimed'] == 0
    monkeypatch.setattr(store, 'delete_owned', original)
    db.engine.dispose()
    assert reconcile_expired(db, store, now=72)['completed'] == 1
    assert reconcile_expired(db, store, now=73)['claimed'] == 0
