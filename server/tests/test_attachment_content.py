import io
import pytest


@pytest.mark.parametrize(('mime','filename','size','data','available','failure','status','expected'), [
    ('text/html','a.html',3,b'<b>',True,'',200,b'<b>'),
    ('image/png','a.png',0,b'',False,'',415,b'{"error":"preview not supported for this file type"}\n'),
    ('text/plain','a.txt',99,b'',False,'',403,b'{"code":"storage_not_configured","error":"storage not configured"}\n'),
    ('text/plain','a.txt',5,b'',True,'',413,b'{"error":"file too large for inline preview"}\n'),
    ('text/plain','a.txt',0,b'12345',True,'',413,b'{"error":"file too large for inline preview"}\n'),
    ('text/plain','a.txt',4,b'1234',True,'',200,b'1234'),
    ('text/plain','a.txt',0,b'',True,'open',404,b'{"error":"attachment object not found"}\n'),
    ('text/plain','a.txt',0,b'',True,'read',502,b'{"error":"failed to read attachment body"}\n'),
])
def test_preview_reads_bounded_bytes_and_preserves_error_order(mime,filename,size,data,available,failure,status,expected):
    from workpal_backend.files.content import render_text_preview
    reads=[];closed=[];opened=[]
    class Reader(io.BytesIO):
        def read(self,n):
            reads.append(n)
            if failure=='read':raise OSError('fixture failure')
            return super().read(min(n,2))
        def close(self):closed.append(True);super().close()
    class Storage:
        def key_from_url(self,url):assert url=='object-url';return 'key'
        def get_reader(self,key):
            opened.append(key)
            if failure=='open':raise OSError('fixture failure')
            return Reader(data)
    att=dict(content_type=mime,filename=filename,size_bytes=size,url='object-url')
    response=render_text_preview(att,Storage() if available else None,max_size=4,frame_ancestors=['https://web.example'])
    assert response.status_code==status and response.body==expected
    if opened and failure!='open':assert closed==[True]
    if status==200:
        assert response.headers['content-type']=='text/plain; charset=utf-8'
        assert response.headers['x-original-content-type']==mime
        assert response.headers['cache-control']=='no-store'
        assert response.headers['x-content-type-options']=='nosniff'
        assert "frame-ancestors 'self' https://web.example" in response.headers['content-security-policy']
    assert all(n<=5 for n in reads)


@pytest.mark.parametrize('failure,status',[('open',404),('read',502),('close',200)])
def test_storage_cancellation_is_an_operation_error_and_close_is_still_attempted(failure,status):
    import asyncio
    from workpal_backend.files.content import render_text_preview
    closed=[]
    class Reader(io.BytesIO):
        def read(self,n):
            if failure=='read':raise asyncio.CancelledError()
            return super().read(n)
        def close(self):
            closed.append(True);super().close()
            if failure=='close':raise asyncio.CancelledError()
    class Storage:
        def key_from_url(self,url):return 'key'
        def get_reader(self,key):
            if failure=='open':raise asyncio.CancelledError()
            return Reader(b'abc')
    response=render_text_preview(dict(content_type='text/plain',filename='a.txt',size_bytes=3,url='object'),Storage())
    assert response.status_code==status
    assert closed==([] if failure=='open' else [True])
