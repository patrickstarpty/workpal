import hashlib
import io
import os
import pytest
from workpal_backend.files.storage import LocalBlobStore, StorageError, SizeLimitExceeded, StorageCollision

@pytest.mark.parametrize('data', [b'', b'abc'])
def test_roundtrip(tmp_path, data):
    s = LocalBlobStore(tmp_path)
    k, lease = s.new_key(), s.new_key()
    with s.create_staging(k, lease) as f:
        assert s.write_bounded(f, io.BytesIO(data), len(data)) == (len(data), hashlib.sha256(data).hexdigest())
    s.sync_and_promote(k, lease)
    with s.open_ready(k) as f:
        assert f.read() == data
    with pytest.raises(StorageCollision):
        s.create_staging(k, lease)
    s.delete_owned(k, lease, ready=True)
    s.delete_owned(k, lease, ready=True)

def test_limits_separation(tmp_path):
    s = LocalBlobStore(tmp_path); k, l = s.new_key(), s.new_key()
    with s.create_staging(k, l) as f:
        with pytest.raises(SizeLimitExceeded): s.write_bounded(f, io.BytesIO(b'ab'), 1)
    with pytest.raises(StorageError): s.open_ready(k)
    s.delete_owned(k, l)

@pytest.mark.parametrize('key', ['../x', '/tmp/x', '', 'a'*31, 'G'*32])
def test_bad_keys(tmp_path, key):
    with pytest.raises(StorageError): LocalBlobStore(tmp_path).open_ready(key)

def test_symlink_and_root_replacement(tmp_path):
    root = tmp_path/'root'; root.mkdir(); s = LocalBlobStore(root)
    k = s.new_key(); (root/(k+'.ready')).symlink_to(tmp_path/'outside')
    with pytest.raises(StorageError): s.open_ready(k)
    root.rename(tmp_path/'old'); root.symlink_to(tmp_path/'old')
    with pytest.raises(StorageError): s.open_ready(k)

@pytest.mark.parametrize('operation', ['write', 'fsync', 'link'])
def test_io_failures_preserve_evidence(tmp_path, monkeypatch, operation):
    s = LocalBlobStore(tmp_path); k,l = s.new_key(), s.new_key()
    def fail(*a, **kw): raise OSError('injected')
    with s.create_staging(k,l) as f:
        if operation == 'write':
            monkeypatch.setattr(os, 'write', fail)
            with pytest.raises(StorageError): s.write_bounded(f, io.BytesIO(b'abc'), 3)
            return
        s.write_bounded(f, io.BytesIO(b'abc'), 3)
    monkeypatch.setattr(os, operation, fail)
    with pytest.raises(StorageError): s.sync_and_promote(k,l)
    assert (tmp_path/(k+'.'+l+'.staging')).exists()

def test_no_overwrite(tmp_path):
    s=LocalBlobStore(tmp_path); k,l=s.new_key(),s.new_key()
    with s.create_staging(k,l) as f: s.write_bounded(f,io.BytesIO(b'a'),1)
    other=s.new_key()
    with s.create_staging(k,other) as f: s.write_bounded(f,io.BytesIO(b'b'),1)
    s.sync_and_promote(k,l)
    with pytest.raises(StorageCollision): s.sync_and_promote(k,other)
    s.delete_owned(k,other)
    with s.open_ready(k) as f: assert f.read()==b'a'

def test_replaced_staging_during_publication_never_succeeds(tmp_path, monkeypatch):
    store = LocalBlobStore(tmp_path)
    key, lease = store.new_key(), store.new_key()
    with store.create_staging(key, lease) as f:
        store.write_bounded(f, io.BytesIO(b'original'), 8)
    link = os.link
    def replace_then_link(source, destination, **kwargs):
        staged = tmp_path / source
        staged.unlink()
        staged.write_bytes(b'replacement')
        return link(source, destination, **kwargs)
    monkeypatch.setattr(os, 'link', replace_then_link)
    with pytest.raises(StorageError, match='replaced'):
        store.sync_and_promote(key, lease)
