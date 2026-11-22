import asyncio
from wsproto import events


def test_keepalive_starts_after_auth_and_unsolicited_pong_moves_only_read_deadline():
    from workpal_backend.realtime.transport import RelayWebSocketProtocol
    class Timer:
        def __init__(self,delay,callback,args):self.delay=delay;self.callback=callback;self.args=args;self.cancelled=False
        def cancel(self):self.cancelled=True
    class Loop:
        def time(self):return 0
        def call_later(self,delay,callback,*args):return Timer(delay,callback,args)
    protocol=RelayWebSocketProtocol.__new__(RelayWebSocketProtocol)
    protocol.loop=Loop();protocol.ping_interval=20;protocol.ping_timeout=20;protocol.last_ping_rtt=0
    protocol.ping_timer=protocol.pong_timer=None;protocol._ping_task=None
    protocol._session_started=False;protocol.handshake_complete=True
    protocol.close_sent=protocol.disconnected=False
    protocol.start_keepalive()
    assert protocol.ping_timer is None and protocol.pong_timer is None
    protocol.start_session(asyncio.Lock())
    ping,deadline=protocol.ping_timer,protocol.pong_timer
    assert ping.delay==54 and deadline.delay==60
    protocol.handle_pong(events.Pong(payload=b'unsolicited'))
    assert deadline.cancelled
    assert protocol.ping_timer is ping
    assert protocol.pong_timer.delay==60
    protocol.stop_keepalive()
    assert ping.cancelled and protocol.ping_timer is None and protocol.pong_timer is None


def test_ping_shares_content_write_lock_and_timeout_aborts_without_control_close():
    from workpal_backend.realtime.transport import RelayWebSocketProtocol
    async def run():
        frames=[]
        class Connection:
            def send(self,event):frames.append(event);return b'ping'
        class Transport:
            closed=False
            writes=[]
            def is_closing(self):return self.closed
            def write(self,data):self.writes.append(data)
            def close(self):self.closed=True
        protocol=RelayWebSocketProtocol.__new__(RelayWebSocketProtocol)
        protocol.loop=asyncio.get_running_loop();protocol.conn=Connection();protocol.transport=Transport()
        protocol.writable=asyncio.Event();protocol.writable.set();protocol.queue=asyncio.Queue()
        protocol.handshake_complete=True;protocol.close_sent=protocol.disconnected=False
        protocol.ping_timer=protocol.pong_timer=None;protocol._ping_task=None
        protocol._session_started=True;protocol._write_lock=asyncio.Lock();protocol.WRITE_WAIT=.02
        await protocol._write_lock.acquire()
        sending=asyncio.create_task(protocol._send_ping())
        await asyncio.sleep(.01)
        assert frames==[]
        protocol._write_lock.release();await sending
        assert len(frames)==1 and isinstance(frames[0],events.Ping) and frames[0].payload==b''
        protocol.writable.clear()
        await protocol._send_ping()
        assert protocol.transport.closed
        assert (await protocol.queue.get())['code']==1006
        assert len(frames)==1
    asyncio.run(run())
