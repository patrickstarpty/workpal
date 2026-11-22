import asyncio
import io
import pytest

ATT=dict(url='stored',filename='report.pdf',content_type='application/pdf',size_bytes=10)
class Storage:
    def __init__(self,reader=None,error=None):self.reader=reader;self.error=error;self.keys=[]
    def get_reader(self,key):
        self.keys.append(key)
        if self.error is not None:raise self.error
        return self.reader


def run(storage,*,attachment=ATT,request_error=lambda:None,**kwargs):
    from workpal_backend.files.proxy import proxy_attachment
    messages=[]
    async def send(message):messages.append(message)
    asyncio.run(proxy_attachment(attachment,storage,'key',send,request_error=request_error,**kwargs))
    return messages[0]['status'],dict(messages[0]['headers']),b''.join(m.get('body',b'') for m in messages[1:])


def test_local_file_uses_actual_size_range_and_closes(tmp_path):
    from workpal_backend.files.local_storage import LocalStorage
    (tmp_path/'key').write_bytes(b'abcde')
    status,headers,body=run(LocalStorage(tmp_path),request_headers={'range':'bytes=1-3'})
    assert status==206 and body==b'bcd'
    assert headers[b'content-range']==b'bytes 1-3/5'
    assert headers[b'content-disposition']==b'inline; filename="report.pdf"'
    assert headers[b'cache-control']==b'no-store'
    assert headers[b'x-content-type-options']==b'nosniff'
    assert b"frame-ancestors 'self' https://app.example" in run(LocalStorage(tmp_path),frame_ancestors=['https://app.example/path'])[1][b'content-security-policy']


def test_nonseekable_storage_uses_recorded_size_and_closes():
    class Reader:
        def __init__(self):self.raw=io.BytesIO(b'abcdefghij');self.closed=False
        def read(self,n):return self.raw.read(n)
        def close(self):self.closed=True
    reader=Reader()
    status,headers,body=run(Storage(reader),request_headers={'range':'bytes=3-5'},force_attachment=True)
    assert status==206 and body==b'def' and reader.closed
    assert headers[b'content-range']==b'bytes 3-5/10'
    assert headers[b'content-disposition']==b'attachment; filename="report.pdf"'


def test_missing_object_and_cancelled_open_have_distinct_responses():
    status,_,body=run(Storage(error=OSError('missing')))
    assert status==404 and body==b'{"error":"attachment object not found"}\n'
    status,_,body=run(Storage(error=asyncio.CancelledError()),request_error=lambda:asyncio.CancelledError())
    assert status==499 and body==b''


def test_cancel_after_open_still_closes_owned_reader():
    reader=io.BytesIO(b'abc')
    status,_,body=run(Storage(reader),request_error=lambda:asyncio.CancelledError())
    assert status==499 and body==b'' and reader.closed


def test_range_error_closes_reader():
    reader=io.BytesIO(b'abc')
    status,_,_=run(Storage(reader),request_headers={'range':'invalid'})
    assert status==416 and reader.closed


def test_send_failure_closes_reader():
    from workpal_backend.files.proxy import proxy_attachment
    reader=io.BytesIO(b'abc')
    async def send(message):raise ConnectionResetError()
    with pytest.raises(ConnectionResetError):asyncio.run(proxy_attachment(ATT,Storage(reader),'key',send))
    assert reader.closed
