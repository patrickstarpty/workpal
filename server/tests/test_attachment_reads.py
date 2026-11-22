import asyncio,io,json,threading
import pytest
from workpal_backend.files.loader import AttachmentLoadError

class Loader:
    def __init__(self,log,failure=0):self.log,self.failure=log,failure
    def load(self,kind,*args):
        self.log.append((kind,args,threading.get_ident()))
        if self.failure:raise AttachmentLoadError(self.failure,'attachment not found')
        return dict(id='attachment',filename='file.txt',url='object',content_type='text/plain',size_bytes=3)
    def for_request(self,*args):return self.load('request',*args)
    def for_download(self,*args):return self.load('download',*args)
class Metadata:
    def __init__(self,log):self.log=log
    async def signed_response(self,attachment):self.log.append(('metadata',attachment['id']));return dict(id=attachment['id'],download_url='signed')
class Storage:
    def __init__(self,log):self.log=log
    def key_from_url(self,url):return url
    def get_reader(self,key):self.log.append(('read',key,threading.get_ident()));return io.BytesIO(b'abc')

def service(log,failure=0):
    from workpal_backend.files.reads import AttachmentReads
    return AttachmentReads(Loader(log,failure),Metadata(log),Storage(log))

@pytest.mark.parametrize('download',[False,True])
def test_metadata_uses_selected_authorization_and_always_mints_fresh_urls(download):
    log=[];main=threading.get_ident()
    response=asyncio.run(service(log).metadata('attachment','workspace','user',for_download=download))
    assert response.status_code==200 and json.loads(response.body)==dict(id='attachment',download_url='signed')
    assert log[0][:2]==(('download',('attachment','user')) if download else ('request',('attachment','workspace')))
    assert log[0][2]!=main and log[1]==('metadata','attachment')

@pytest.mark.parametrize('operation',['metadata','content'])
@pytest.mark.parametrize('status',[404,499])
def test_loading_failure_never_opens_storage_or_mints_signature(operation,status):
    log=[];reader=service(log,status)
    response=asyncio.run(reader.metadata('attachment','workspace','user') if operation=='metadata' else reader.content('attachment','workspace'))
    assert response.status_code==status and len(log)==1
    if status==499:assert response.body==b''


def test_content_authorizes_then_reads_off_loop_and_returns_bounded_text():
    log=[];main=threading.get_ident()
    response=asyncio.run(service(log).content('attachment','workspace'))
    assert response.status_code==200 and response.body==b'abc'
    assert [entry[0] for entry in log]==['request','read']
    assert all(entry[2]!=main for entry in log)
