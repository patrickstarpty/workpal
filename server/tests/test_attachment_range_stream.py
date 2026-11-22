import asyncio
import pytest


@pytest.mark.parametrize(('header', 'size', 'data', 'status', 'body', 'content_range'), [
    ('bytes=2-4', 10, b'0123456789', 206, b'234', 'bytes 2-4/10'),
    ('bytes=-3', 10, b'0123456789', 206, b'789', 'bytes 7-9/10'),
    ('bytes=0-1,4-5', 10, b'0123456789', 200, b'0123456789', None),
    ('bytes=10-', 10, b'0123456789', 416, b'{"error":"requested range not satisfiable"}\n', 'bytes */10'),
    ('bytes=5-', 10, b'012', 502, b'{"error":"failed to read attachment range"}\n', None),
    ('', -1, b'abc', 200, b'abc', None),
    ('bytes=0-invalid', 0, b'', 200, b'', None),
])
def test_forward_only_response(header, size, data, status, body, content_range):
    from workpal_backend.files.range_stream import serve_proxy_range
    async def run():
        chunks=[];starts=[]
        class Reader:
            position=0
            async def read(self,n):
                result=data[self.position:self.position+min(n,2)]
                self.position+=len(result)
                return result
        async def send(message):
            if message['type']=='http.response.start':starts.append(message)
            else:chunks.append(message['body'])
        await serve_proxy_range(Reader(),size,header,send)
        assert len(starts)==1
        response=starts[0];headers=dict(response['headers'])
        assert response['status']==status
        assert b''.join(chunks)==body
        assert headers[b'accept-ranges']==b'bytes'
        assert headers.get(b'content-range')==(content_range.encode() if content_range else None)
        if size<0 and status==200:assert b'content-length' not in headers
        else:assert int(headers[b'content-length'])==len(body)
    asyncio.run(run())


def test_transport_write_failure_does_not_attempt_another_body_write():
    from workpal_backend.files.range_stream import serve_proxy_range
    async def run():
        attempts=[]
        class Reader:
            async def read(self,n):return b'abc'
        async def send(message):
            attempts.append(message)
            if message['type']=='http.response.body':raise BrokenPipeError('closed peer')
        await serve_proxy_range(Reader(),3,'bytes=0-2',send)
        assert [m['type'] for m in attempts]==['http.response.start','http.response.body']
    asyncio.run(run())
