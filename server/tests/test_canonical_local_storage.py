"""Canonical local storage operates only on these isolated temporary fixtures."""
import io
import json
import pytest


def test_upload_sidecar_replace_and_delete(tmp_path):
    from workpal_backend.files.local_storage import LocalStorage
    store=LocalStorage(tmp_path,'https://files.example/')
    assert store.upload('users/u/a.png',b'first','image/png','display.png')=='https://files.example/uploads/users/u/a.png'
    with store.get_reader('users/u/a.png') as reader:assert reader.read()==b'first'
    assert json.loads((tmp_path/'users/u/a.png.meta.json').read_text())=={'filename':'display.png','content_type':'image/png'}
    store.upload_stream('users/u/a.png',io.BytesIO(b'second'),999,'image/png','')
    assert (tmp_path/'users/u/a.png').read_bytes()==b'second'
    assert (tmp_path/'users/u/a.png.meta.json').exists()
    (tmp_path/'users/u/.a.png.tmp').write_bytes(b'crash')
    store.delete_object('users/u/a.png')
    assert list((tmp_path/'users/u').iterdir())==[]
    store.delete_object('users/u/a.png')


def test_failed_stream_preserves_existing_and_removes_temp(tmp_path):
    from workpal_backend.files.local_storage import LocalStorage
    store=LocalStorage(tmp_path)
    store.upload('a',b'original','text/plain','original.txt')
    class Broken:
        def __init__(self):self.first=True
        def read(self,size=-1):
            if self.first:self.first=False;return b'partial'
            raise OSError('fixture read failure')
    with pytest.raises(OSError):store.upload_stream('a',Broken(),100,'new/type','new.txt')
    assert (tmp_path/'a').read_bytes()==b'original'
    assert json.loads((tmp_path/'a.meta.json').read_text())['filename']=='original.txt'
    assert not (tmp_path/'.a.tmp').exists()


@pytest.mark.parametrize('key',['','../outside','a.meta.json','.a.tmp','nested/.a.tmp'])
def test_reader_rejects_internal_and_escaping_keys(tmp_path,key):
    from workpal_backend.files.local_storage import LocalStorage
    with pytest.raises(OSError):LocalStorage(tmp_path).get_reader(key)


def test_reader_allows_regular_tmp_and_dot_png(tmp_path):
    from workpal_backend.files.local_storage import LocalStorage
    store=LocalStorage(tmp_path)
    for key in ['notes.tmp','.avatar.png']:
        store.upload(key,b'body','','')
        with store.get_reader(key) as reader:assert reader.read()==b'body'


def test_temp_creation_failure_does_not_remove_existing_directory(tmp_path,monkeypatch):
    from workpal_backend.files.local_storage import LocalStorage
    removed=[]
    monkeypatch.setattr('workpal_backend.files.local_storage.remove',lambda path:removed.append(path))
    (tmp_path/'.a.tmp').mkdir()
    with pytest.raises(OSError):LocalStorage(tmp_path).upload('a',b'data')
    assert (tmp_path/'.a.tmp').is_dir()
    assert removed==[]


def test_upload_from_reader_reads_until_eof_before_writing(tmp_path):
    from workpal_backend.files.local_storage import LocalStorage
    class Chunks:
        def __init__(self):self.values=iter([b'first',b'second',b''])
        def read(self,size=-1):return next(self.values)
    LocalStorage(tmp_path).upload_from_reader('a',Chunks())
    assert (tmp_path/'a').read_bytes()==b'firstsecond'
