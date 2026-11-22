import asyncio
import pytest
from workpal_backend.realtime.relay_consumer import _operation, _Stopped


def test_completed_write_cannot_swallow_stop_and_enter_blocking_read():
    from workpal_backend.infrastructure.redis_cancellation import CancellationWriteGuard
    async def run():
        loop=asyncio.get_running_loop();written=loop.create_future();entered=asyncio.Event();reading=[];closed=[]
        class Dependency:
            async def send_packed_command(self,*args,**kwargs):
                entered.set()
                await asyncio.wait_for(written,60)
            async def disconnect(self,**kwargs):closed.append(kwargs)
        class Connection(CancellationWriteGuard,Dependency):pass
        connection=Connection();stop=asyncio.Event()
        async def command():
            await connection.send_packed_command(b'command')
            reading.append(True)
            await asyncio.Event().wait()
        operation=asyncio.create_task(_operation(command(),stop,60))
        await entered.wait()
        stop.set()
        # Complete the inner write between stop wake-up and Task.cancel().
        # Python 3.11 wait_for returns its result despite the outer cancel.
        loop.call_soon(written.set_result,None)
        with pytest.raises(_Stopped):
            await asyncio.wait_for(operation,.5)
        assert reading==[]
        assert closed==[{'nowait':True}]
        assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    asyncio.run(run())
