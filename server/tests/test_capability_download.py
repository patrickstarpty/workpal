import asyncio
import io
from urllib.parse import urlsplit
import pytest
from workpal_backend.files.capabilities import AttachmentCapabilities
from workpal_backend.infrastructure.query_errors import NoRows
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
CAPS=AttachmentCapabilities('public-test-fixture')
class Queries:
    def __init__(self,missing=False):self.calls=[];self.missing=missing
    def get_attachment_by_id(self,identity):
        self.calls.append(identity)
        if self.missing:raise NoRows()
        return dict(id=A,url='object',filename='image.png',content_type='image/png',size_bytes=3)
class Storage:
    def __init__(self):self.reader=io.BytesIO(b'abc')
    def key_from_url(self,url):return 'key'
    def get_reader(self,key):return self.reader

def run(identity=A,query=None,queries=None,storage=True):
    from workpal_backend.files.capability_download import redeem_attachment
    q=queries or Queries();store=Storage() if storage is True else storage;messages=[]
    async def send(message):messages.append(message)
    raw=urlsplit(CAPS.path(identity,now_ns=100*10**9)).query.encode() if query is None else query
    asyncio.run(redeem_attachment(identity,raw,q,store,CAPS,send,clock_ns=lambda:100*10**9))
    return q,store,messages[0]['status'],dict(messages[0]['headers']),b''.join(m.get('body',b'') for m in messages[1:])

@pytest.mark.parametrize('query',[b'',b'exp=1&sig=bad',b'exp=&exp=160&sig=bad'])
def test_invalid_capability_never_queries_database(query):
    q,_,status,_,body=run(query=query)
    assert status==403 and body==b'{"error":"invalid or expired download link"}\n' and not q.calls


def test_valid_signature_precedes_uuid_parsing():
    q,_,status,_,body=run(identity='not-a-uuid')
    assert status==400 and body==b'{"error":"invalid attachment id"}\n' and not q.calls


def test_capability_redeems_without_membership_lookup_and_protects_referrer():
    q,storage,status,headers,body=run()
    assert q.calls==[A] and status==200 and body==b'abc' and storage.reader.closed
    assert headers[b'referrer-policy']==b'no-referrer'
    assert headers[b'content-disposition']==b'inline; filename="image.png"'
    assert b'content-security-policy' in headers


def test_download_intent_is_bound_to_signature():
    query=urlsplit(CAPS.path(A,now_ns=100*10**9)).query.encode()
    q,_,status,_,_=run(query=query+b'&dl=1')
    assert status==403 and not q.calls
    query=urlsplit(CAPS.path(A,now_ns=100*10**9,download=True)).query.encode()
    _,_,status,headers,_=run(query=query)
    assert status==200 and headers[b'content-disposition']==b'attachment; filename="image.png"'


def test_valid_capability_missing_attachment_precedes_storage_configuration():
    _,_,status,_,body=run(queries=Queries(missing=True),storage=None)
    assert status==404 and body==b'{"error":"attachment not found"}\n'
    _,_,status,_,body=run(storage=None)
    assert status==403 and b'storage_not_configured' in body


def test_open_failure_retains_capability_referrer_and_csp():
    class Broken(Storage):
        def get_reader(self,key):raise OSError('missing')
    _,_,status,headers,_=run(storage=Broken())
    assert status==404 and headers[b'referrer-policy']==b'no-referrer' and b'content-security-policy' in headers
