"""wsproto transport extension for Go's immediate connection close.

ASGI's ordinary websocket.close sends a control frame. The relay also needs
net.Conn.Close semantics after failed authorization, including under write
backpressure. The CLI selects this protocol explicitly.
"""
from uvicorn.protocols.websockets.wsproto_impl import WSProtocol
from copy import copy
import asyncio
from wsproto import events
from wsproto.frame_protocol import Frame, FrameDecoder, MessageDecoder, Opcode, ParseFailed, CloseReason

ABORT_EXTENSION = 'workpal.websocket.abort'
RAW_TEXT_EXTENSION = 'workpal.websocket.raw_text'
SESSION_EXTENSION = 'workpal.websocket.session'


class _OpaqueText(str):
    """Keep Go text-frame bytes through wsproto's str.encode boundary.

    wsproto selects TEXT for str and delegates framing/compression to its
    normal state machine. The source backend does not validate outbound UTF-8.
    """
    def __new__(cls, raw):
        value = super().__new__(cls, raw.decode('utf-8', errors='surrogateescape'))
        value.raw = raw
        return value

    def encode(self, encoding='utf-8', errors='strict'):
        if encoding == 'utf-8' and errors == 'strict':
            return self.raw
        return super().encode(encoding, errors)


class _ByteMessageDecoder(MessageDecoder):
    """Gorilla leaves data-message UTF-8 validation to the application.

    Keep the standard continuation validation and control-frame handling;
    expose data payloads to ASGI as bytes for the Go-compatible JSON decoder.
    """
    def process_frame(self, frame):
        if frame.opcode is Opcode.TEXT:
            frame = Frame(Opcode.BINARY, frame.payload, frame.frame_finished, frame.message_finished)
        return super().process_frame(frame)


class _LimitedFrameDecoder(FrameDecoder):
    def __init__(self, client, extensions, too_large):
        super().__init__(client, extensions)
        self.too_large = too_large
        self.message_size = 0
        self.fragmented = False

    def parse_header(self):
        if not super().parse_header():
            return False
        header = self.header
        if header.opcode.iscontrol():
            return True
        if header.opcode is Opcode.CONTINUATION:
            if not self.fragmented:
                raise ParseFailed('unexpected CONTINUATION')
        else:
            if self.fragmented:
                raise ParseFailed('expected CONTINUATION')
            self.message_size = 0
        self.fragmented = not header.fin
        self.message_size += header.payload_len
        if self.message_size > 64 * 1024:
            self.too_large()
            raise ParseFailed('', CloseReason.MESSAGE_TOO_BIG)
        return True


class RelayWebSocketProtocol(WSProtocol):
    PING_PERIOD = 54
    PONG_WAIT = 60
    WRITE_WAIT = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = copy(self.config)
        # Gorilla's upstream upgrader does not enable compression.
        self.config.ws_per_message_deflate = False
        self._inbound_too_large = False
        self._session_started = False
        self._ping_task = None

    def start_keepalive(self):
        # Uvicorn invokes this at upgrade, before first-message auth. Go starts
        # its read/write pumps only after authentication and Hub registration.
        pass

    def start_session(self, write_lock):
        if self._session_started or self.disconnected or self.close_sent:
            return
        self._session_started = True
        self._write_lock = write_lock
        self._next_ping = self.loop.time() + self.PING_PERIOD
        self.ping_timer = self.loop.call_later(self.PING_PERIOD, self.send_keepalive_ping)
        self._reset_read_deadline()

    def _reset_read_deadline(self):
        if self.pong_timer is not None:
            self.pong_timer.cancel()
        self.pong_timer = self.loop.call_later(self.PONG_WAIT, self._abort_transport)

    def handle_pong(self, event):
        if self._session_started and not self.disconnected and not self.close_sent:
            self._reset_read_deadline()

    def send_keepalive_ping(self):
        if not self._session_started or self.disconnected or self.close_sent:
            return
        now = self.loop.time()
        self._next_ping += max(1, int((now - self._next_ping) // self.PING_PERIOD) + 1) * self.PING_PERIOD
        self.ping_timer = self.loop.call_later(max(0, self._next_ping - now), self.send_keepalive_ping)
        if self._ping_task is None or self._ping_task.done():
            self._ping_task = self.loop.create_task(self._send_ping())
            self.tasks.add(self._ping_task)
            self._ping_task.add_done_callback(self.tasks.discard)

    async def _send_ping(self):
        try:
            async with self._write_lock:
                if self.disconnected or self.close_sent:
                    return
                async with asyncio.timeout(self.WRITE_WAIT):
                    await self.writable.wait()
                    if not self.transport.is_closing():
                        self.transport.write(self.conn.send(events.Ping(payload=b'')))
        except Exception:
            self._abort_transport()

    def stop_keepalive(self):
        super().stop_keepalive()
        task = self._ping_task
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()

    def _abort_transport(self):
        if not self.disconnected:
            self.close_sent = True
            self.disconnected = True
            self.stop_keepalive()
            self.writable.set()
            self.queue.put_nowait({'type': 'websocket.disconnect', 'code': 1006})
            self.transport.close()

    def _mark_too_large(self):
        self._inbound_too_large = True

    def handle_close(self, event):
        if self._inbound_too_large and not self.close_sent:
            self.close_sent = True
            self.stop_keepalive()
            if not self.transport.is_closing():
                self.transport.write(self.conn.send(event.response()))
            self.queue.put_nowait({'type': 'websocket.disconnect', 'code': 1009,
                                   'workpal.too_large': True})
            self.transport.close()
            return
        super().handle_close(event)

    async def run_asgi(self):
        # Capture the actual TCP peer before Uvicorn's proxy middleware can
        # rewrite scope.client from X-Forwarded-For. Go checks RemoteAddr.
        self.scope['workpal.peer'] = self.client
        self.scope.setdefault('extensions', {})[ABORT_EXTENSION] = {}
        self.scope['extensions'][RAW_TEXT_EXTENSION] = {}
        self.scope['extensions'][SESSION_EXTENSION] = {}
        await super().run_asgi()

    async def send(self, message):
        if message['type'] == 'websocket.close' and message.get('workpal.abort'):
            if not self.handshake_complete:
                raise RuntimeError('WebSocket TCP close requires an accepted handshake')
            self._abort_transport()
            return
        if message['type'] == 'websocket.send' and 'workpal.session' in message:
            if not self.handshake_complete:
                raise RuntimeError('WebSocket session requires an accepted handshake')
            self.start_session(message['workpal.session'])
            return
        if message['type'] == 'websocket.send' and message.get('workpal.text'):
            message = {'type': 'websocket.send', 'text': _OpaqueText(message['bytes'])}
        await super().send(message)
        if message['type'] == 'websocket.accept':
            # wsproto creates FrameProtocol during the accept. Install before
            # returning to the event loop, so the first data frame is raw too.
            protocol = self.conn.connection._proto
            protocol._message_decoder = _ByteMessageDecoder()
            protocol._frame_decoder = _LimitedFrameDecoder(protocol.client, protocol.extensions, self._mark_too_large)
