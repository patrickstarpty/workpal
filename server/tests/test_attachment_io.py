import asyncio
import io
import threading
import pytest


def test_sync_reader_is_accessed_off_event_loop_and_closed():
    from workpal_backend.files.attachment_io import open_attachment_reader
    thread=threading.get_ident();calls=[]
    class Reader(io.BytesIO):
        def read(self,n):calls.append(threading.get_ident());return super().read(n)
        def seek(self,*args):calls.append(threading.get_ident());return super().seek(*args)
        def close(self):calls.append(threading.get_ident());super().close()
    raw=Reader(b'abcdef')
    class Storage:
        def get_reader(self,key):assert key=='object';calls.append(threading.get_ident());return raw
    async def exercise():
        reader=await open_attachment_reader(Storage(),'object')
        assert reader.seekable
        assert await reader.seek(2)==2
        assert await reader.read(2)==b'cd'
        await reader.close()
    asyncio.run(exercise())
    assert raw.closed and calls and all(value!=thread for value in calls)


def test_cancelled_open_joins_worker_and_closes_result():
    from workpal_backend.files.attachment_io import open_attachment_reader
    opened=threading.Event();release=threading.Event();raw=io.BytesIO(b'x')
    class Storage:
        def get_reader(self,key):opened.set();release.wait(5);return raw
    async def exercise():
        task=asyncio.create_task(open_attachment_reader(Storage(),'object'))
        await asyncio.to_thread(opened.wait,2)
        task.cancel();await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):await task
        assert raw.closed
    try:asyncio.run(exercise())
    finally:release.set()


def test_cancelled_read_finishes_before_reader_can_close():
    from workpal_backend.files.attachment_io import open_attachment_reader
    entered=threading.Event();release=threading.Event();order=[]
    class Reader:
        def read(self,n):entered.set();release.wait(5);order.append('read');return b'x'
        def close(self):order.append('close')
    class Storage:
        def get_reader(self,key):return Reader()
    async def exercise():
        reader=await open_attachment_reader(Storage(),'object')
        assert not reader.seekable
        task=asyncio.create_task(reader.read(1))
        await asyncio.to_thread(entered.wait,2)
        task.cancel();await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):await task
        await reader.close()
        assert order==['read','close']
    try:asyncio.run(exercise())
    finally:release.set()
