import asyncio,json
from concurrent.futures import ThreadPoolExecutor
from workpal_backend.realtime.dedup import SeenEvents
from workpal_backend.realtime.hub import Hub,Connection


def test_fifo_window_does_not_refresh_duplicates_and_empty_bypasses():
    seen=SeenEvents()
    assert seen.mark('') and seen.mark('')
    for index in range(128):assert seen.mark(str(index))
    assert not seen.mark('0')
    assert seen.mark('128')
    assert seen.mark('0')  # Duplicate access did not refresh the oldest entry.
    assert not seen.mark('128')


def test_concurrent_duplicate_has_exactly_one_first_delivery():
    seen=SeenEvents()
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(seen.mark,['same']*200))==1


def test_hub_dedup_is_per_connection_and_only_after_audience_selection():
    class Socket:
        def __init__(self):self.frames=[]
        async def send_text(self,raw):self.frames.append(json.loads(raw))
        async def close(self,code):pass
    async def run():
        h=Hub();a,b=Socket(),Socket()
        first=Connection(a,lambda:None,'w','u');second=Connection(b,lambda:None,'w','v')
        h.connections.update([first,second])
        event=dict(type='chat:message',workspaceID='w',chatSessionOwnerID='u',payload='first')
        await h.publish(event,event_id='id');await h.publish(event,event_id='id')
        assert len(a.frames)==1 and not b.frames
        event['chatSessionOwnerID']='v';await h.publish(event,event_id='id')
        assert len(b.frames)==1
        fresh=Socket();h.connections.add(Connection(fresh,lambda:None,'w','u'))
        event['chatSessionOwnerID']='u';await h.publish(event,event_id='id')
        assert len(a.frames)==1 and len(fresh.frames)==1
        await h.publish(event);await h.publish(event)
        assert len(a.frames)==3 and len(fresh.frames)==3
    asyncio.run(run())
