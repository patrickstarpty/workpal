import asyncio
import io
import pytest

class Reader:
    def __init__(self,body):self.file=io.BytesIO(body);self.calls=[]
    async def seek(self,offset,whence=0):self.calls.append(('seek',offset,whence));return self.file.seek(offset,whence)
    async def read(self,size):self.calls.append(('read',size));return self.file.read(size)


def run(body=b'abcdefghij',headers=None,method='GET'):
    from workpal_backend.files.seekable_content import serve_seekable_attachment
    reader=Reader(body);messages=[]
    async def send(message):messages.append(message)
    asyncio.run(serve_seekable_attachment(reader,send,method=method,request_headers=headers or {},headers={b'content-type':b'text/plain',b'cache-control':b'no-store',b'content-disposition':b'attachment'}))
    return reader,messages[0]['status'],dict(messages[0]['headers']),b''.join(m.get('body',b'') for m in messages[1:])

@pytest.mark.parametrize(('value','status','body'),[('',200,b'abcdefghij'),('bytes=2-4',206,b'cde'),('bytes=-0',206,b''),('bytes=',200,b'abcdefghij'),('bytes=99-100,0-1',206,b'ab'),('bytes=0-9,0-9',200,b'abcdefghij')])
def test_seekable_range_success(value,status,body):
    _,actual,headers,data=run(headers={'range':value})
    assert actual==status and data==body
    assert headers[b'content-length']==str(len(body)).encode()
    assert headers[b'accept-ranges']==b'bytes'


def test_multi_range_body_contains_ordered_parts_and_exact_length():
    _,status,headers,data=run(headers={'range':'bytes=0-1,4-5'})
    assert status==206
    boundary=headers[b'content-type'].split(b'boundary=')[1]
    expected=(b'--'+boundary+b'\r\nContent-Range: bytes 0-1/10\r\nContent-Type: text/plain\r\n\r\nab\r\n--'+boundary+b'\r\nContent-Range: bytes 4-5/10\r\nContent-Type: text/plain\r\n\r\nef\r\n--'+boundary+b'--\r\n')
    assert data==expected
    assert int(headers[b'content-length'])==len(data)

@pytest.mark.parametrize(('value','message','content_range'),[('items=0-1',b'invalid range\n',None),('bytes=99-',b'invalid range: failed to overlap\n',b'bytes */10')])
def test_range_errors_clear_cache_control(value,message,content_range):
    _,status,headers,body=run(headers={'range':value})
    assert status==416 and body==message
    assert b'cache-control' not in headers
    assert headers[b'content-type']==b'text/plain; charset=utf-8'
    assert headers.get(b'content-range')==content_range
    assert headers[b'content-disposition']==b'attachment'


def test_head_uses_size_without_reading_body():
    reader,status,headers,body=run(headers={'range':'bytes=0-1,4-5'},method='HEAD')
    assert status==206 and body==b'' and int(headers[b'content-length'])>4
    assert all(call[0]=='seek' for call in reader.calls)

@pytest.mark.parametrize(('method','headers','status'),[
    ('GET',{'if-match':'"other"'},412),
    ('GET',{'if-none-match':'*'},304),
    ('POST',{'if-none-match':'*'},412),
    ('GET',{'if-match':'*','if-none-match':'"other"'},200),
    ('GET',{'range':'bytes=0-1','if-range':'"other"'},200),
    ('POST',{'range':'bytes=0-1','if-range':'"other"'},206),
])
def test_preconditions_without_etag_or_modification_time(method,headers,status):
    reader,actual,response,body=run(headers=headers,method=method)
    assert actual==status
    if status in (304,412):assert not reader.calls and body==b''
    if status==304:assert b'content-type' not in response


def test_empty_file_out_of_bounds_is_ignored():
    _,status,headers,body=run(b'',{'range':'bytes=99-'})
    assert status==200 and body==b'' and headers[b'content-length']==b'0'


def test_more_than_200_ranges_are_ignored_before_validation():
    _,status,_,body=run(headers={'range':'bytes='+','.join(['invalid']*201)})
    assert status==200 and body==b'abcdefghij'


@pytest.mark.parametrize('space',['\t','\r','\n',' '])
def test_go_textproto_ascii_whitespace_in_ranges_and_entity_tags(space):
    _,status,_,body=run(headers={'range':'bytes='+space+'0-1'+space})
    assert status==206 and body==b'ab'
    _,status,_,body=run(headers={'if-match':space+'*'+space})
    assert status==200 and body==b'abcdefghij'
