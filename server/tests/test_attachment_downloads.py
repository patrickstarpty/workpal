import asyncio
import io
import pytest

ATT=dict(url='https://cdn.example/file',filename='report.pdf',content_type='application/pdf',size_bytes=3)
class Loader:
    def __init__(self,error=None):self.error=error;self.calls=[]
    def for_download(self,identity,user):
        self.calls.append((identity,user))
        if self.error:raise self.error
        return ATT
class Storage:
    def __init__(self):self.calls=[];self.reader=None
    def key_from_url(self,url):self.calls.append(('key',url));return 'key'
    def get_reader(self,key):self.calls.append(('read',key));self.reader=io.BytesIO(b'abc');return self.reader
class Presigner(Storage):
    def presign_get_with_content_disposition(self,key,ttl,disposition):
        self.calls.append(('presign',key,ttl,disposition));return 'https://cdn.example/signed'
class Signer:
    def __init__(self):self.calls=[]
    def signed_url_with_content_disposition(self,*args):self.calls.append(args);return 'https://cdn.example/signed'

def run(loader=None,storage=None,**kwargs):
    from workpal_backend.files.downloads import AttachmentDownloads
    messages=[]
    async def send(message):messages.append(message)
    service=AttachmentDownloads(loader or Loader(),storage,clock_ns=lambda:100_000_000_000,**kwargs)
    asyncio.run(service.download('attachment','user',send))
    return messages[0]['status'],dict(messages[0]['headers']),b''.join(m.get('body',b'') for m in messages[1:])


def test_loader_denial_precedes_storage_or_redirect():
    from workpal_backend.files.loader import AttachmentLoadError
    storage=Storage()
    status,_,body=run(Loader(AttachmentLoadError(404,'attachment not found')),storage)
    assert status==404 and body==b'{"error":"attachment not found"}\n' and not storage.calls


def test_disabled_storage_returns_explicit_feature_error():
    status,_,body=run()
    assert status==403 and body==b'{"code":"storage_not_configured","error":"storage not configured"}\n'


def test_cloudfront_redirect_forces_attachment_and_uses_configured_ttl():
    signer=Signer();storage=Storage()
    status,headers,body=run(storage=storage,signer=signer,ttl_nanoseconds=5_500_000_000,frame_ancestors=['https://app.example'])
    assert status==302 and headers[b'location']==b'https://cdn.example/signed'
    assert signer.calls==[(ATT['url'],'attachment; filename="report.pdf"',105)]
    assert storage.calls==[('key',ATT['url'])]
    assert b'https://app.example' in headers[b'content-security-policy']
    assert body==b'<a href="https://cdn.example/signed">Found</a>.\n\n'


def test_public_presigner_uses_default_ttl():
    storage=Presigner()
    status,_,_=run(storage=storage)
    assert status==302
    assert storage.calls[-1]==('presign','key',1800*10**9,'attachment; filename="report.pdf"')

@pytest.mark.parametrize(('mode','message'),[('cloudfront','cloudfront attachment downloads are not configured'),('presign','attachment storage does not support presigned downloads')])
def test_explicit_unsupported_mode_errors(mode,message):
    status,_,body=run(storage=Storage(),mode=mode)
    assert status==500 and message.encode() in body


def test_presigner_failure_returns_502():
    class Broken(Presigner):
        def presign_get_with_content_disposition(self,*args):raise OSError('sign failed')
    status,_,body=run(storage=Broken())
    assert status==502 and body==b'{"error":"failed to create download URL"}\n'


def test_explicit_proxy_ignores_available_signer_and_closes_reader():
    signer=Signer();storage=Presigner()
    status,_,body=run(storage=storage,signer=signer,mode='proxy')
    assert status==200 and body==b'abc' and storage.reader.closed
    assert signer.calls==[] and storage.calls[-1]==('read','key')
