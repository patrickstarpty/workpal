import asyncio


def test_frames_arriving_during_lookup_require_a_new_authorization():
    from workpal_backend.realtime.writer import QueuedWriter
    async def run():
        querying=asyncio.Event();release=asyncio.Event();writes=[];lookups=[];failed=[]
        async def authorize():
            lookups.append(True)
            if len(lookups)==1:
                querying.set();await release.wait()
            else:raise PermissionError('revoked')
        async def write(frame):writes.append(frame)
        async def failure():failed.append(True)
        writer=QueuedWriter(authorize,write,failure)
        assert writer.try_send(b'before')
        await querying.wait()
        assert writer.try_send(b'after')
        release.set();await writer.flush()
        await asyncio.sleep(0)
        assert writes==[b'before'] and len(lookups)==2 and failed==[True]
        assert not writer.try_send(b'late')
        await writer.stop()
    asyncio.run(run())


def test_batch_limit_and_queue_capacity_are_independent():
    from workpal_backend.realtime.writer import QueuedWriter
    async def run():
        writes=[];batch_sizes=[]
        async def authorize():batch_sizes.append(len(writes))
        async def write(frame):writes.append(frame)
        async def failure():raise AssertionError('unexpected failure')
        writer=QueuedWriter(authorize,write,failure)
        for i in range(256):assert writer.try_send(str(i).encode())
        assert not writer.try_send(b'overflow')
        await writer.flush()
        assert batch_sizes==[0,32,64,96,128,160,192,224]
        assert writes==[str(i).encode() for i in range(256)]
        await writer.stop()
        assert not writer.try_send(b'closed')
    asyncio.run(run())


def test_stop_during_lookup_discards_captured_and_queued_content():
    from workpal_backend.realtime.writer import QueuedWriter
    async def run():
        entered=asyncio.Event();writes=[]
        async def authorize():entered.set();await asyncio.Event().wait()
        async def write(frame):writes.append(frame)
        async def failure():pass
        writer=QueuedWriter(authorize,write,failure)
        writer.try_send(b'captured');await entered.wait();writer.try_send(b'queued')
        await writer.stop();await asyncio.wait_for(writer.flush(),.2)
        assert writes==[]
    asyncio.run(run())


def test_write_failure_discards_rest_of_batch_and_next_batches():
    from workpal_backend.realtime.writer import QueuedWriter
    async def run():
        attempted=[];failed=[]
        async def authorize():pass
        async def write(frame):
            attempted.append(frame)
            if frame==b'1':raise OSError('closed transport')
        async def failure():failed.append(True)
        writer=QueuedWriter(authorize,write,failure)
        for i in range(70):writer.try_send(str(i).encode())
        await writer.flush();await asyncio.sleep(0)
        assert attempted==[b'0',b'1'] and failed==[True]
        await writer.stop()
    asyncio.run(run())


def test_connection_enqueue_returns_before_membership_lookup_and_close_cancels_writer():
    from workpal_backend.realtime.hub import Connection,Hub
    from threading import Event
    async def run():
        entered=Event();release=Event();writes=[]
        class Socket:
            async def send_text(self,frame):writes.append(frame)
            async def close(self,code):pass
        def check():entered.set();release.wait(2)
        c=Connection(Socket(),check,'w','u');h=Hub();h.register(c)
        try:
            assert c.enqueue({'type':'pong'})
            assert not entered.is_set()
            async with asyncio.timeout(1):
                while not entered.is_set():await asyncio.sleep(.001)
            await c.close()
            assert not h.connections and writes==[]
            assert not c.enqueue({'type':'pong'})
        finally:release.set()
    asyncio.run(run())


def test_finish_rejects_new_frames_but_drains_old_batches_before_close():
    from workpal_backend.realtime.writer import QueuedWriter
    async def run():
        writes=[];lookups=[];events=[]
        async def authorize():lookups.append(len(writes))
        async def write(frame):writes.append(frame)
        async def failure():events.append('failed')
        async def drained():events.append(('drained',len(writes)))
        writer=QueuedWriter(authorize,write,failure,on_drained=drained)
        for i in range(65):assert writer.try_send(str(i).encode())
        writer.finish();writer.finish()
        assert not writer.try_send(b'late')
        await writer.flush()
        assert lookups==[0,32,64] and writes==[str(i).encode() for i in range(65)]
        assert events==[('drained',65)]
        await writer.stop()
    asyncio.run(run())


def test_finish_wakes_idle_writer_and_abort_never_reports_successful_drain():
    from workpal_backend.realtime.writer import QueuedWriter
    async def run():
        events=[]
        async def noop(*args):pass
        async def drained():events.append('drained')
        writer=QueuedWriter(noop,noop,noop,on_drained=drained)
        writer.finish();await asyncio.wait_for(writer.flush(),.2)
        assert events==['drained']
        writer=QueuedWriter(noop,noop,noop,on_drained=drained)
        writer.try_send(b'discard');await writer.stop();writer.finish()
        await writer.flush()
        assert events==['drained']
    asyncio.run(run())
