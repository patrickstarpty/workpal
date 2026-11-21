"""Single API process internal-stream bridge; at-least-once snapshot fanout."""
import asyncio
import json
import logging
from sqlalchemy import Column, MetaData, String, Table, select
from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool
from ..infrastructure.database import DatabaseBusy
from .protocol import project_event, ProjectionError

metadata = MetaData()
checkpoints = Table('realtime_consumer_checkpoint', metadata,
    Column('consumer', String, primary_key=True), Column('stream_id', String, nullable=False))
receipts = Table('realtime_consumer_receipt', metadata,
    Column('consumer', String, primary_key=True), Column('event_id', String, primary_key=True))
quarantine = Table('realtime_consumer_quarantine', metadata,
    Column('consumer', String, primary_key=True), Column('stream_id', String, primary_key=True),
    Column('reason', String, nullable=False))
log = logging.getLogger(__name__)

class RealtimeConsumer:
    def __init__(self, database, resources, hub, *, consumer='api', timeout=1, retry_delay=.1):
        if not 0 < timeout <= 5 or not 0 < retry_delay <= 5:
            raise ValueError('Invalid consumer bounds')
        self.database, self.client, self.hub = database, resources.client, hub
        self.channel = resources.key('events:stream')
        self.consumer = consumer
        self.timeout, self.retry_delay = timeout, retry_delay
        self._stop = asyncio.Event()
        self._running = False

    def stop(self):
        self._stop.set()

    def _position(self):
        with self.database.transaction() as s:
            return s.execute(select(checkpoints.c.stream_id).where(checkpoints.c.consumer == self.consumer)).scalar_one_or_none() or '0-0'

    def _commit(self, stream_id, event_id=None, reason=None):
        with self.database.transaction() as s:
            s.execute(checkpoints.delete().where(checkpoints.c.consumer == self.consumer))
            s.execute(checkpoints.insert().values(consumer=self.consumer, stream_id=stream_id))
            if event_id:
                s.execute(receipts.insert().values(consumer=self.consumer, event_id=event_id))
            if reason:
                s.execute(quarantine.insert().values(consumer=self.consumer, stream_id=stream_id, reason=reason))

    def _seen(self, event_id):
        with self.database.transaction() as s:
            return s.execute(select(receipts.c.event_id).where(receipts.c.consumer == self.consumer, receipts.c.event_id == event_id)).first() is not None

    async def tick(self):
        """Read at most one entry. No SQL transaction spans any await."""
        if self._stop.is_set():
            return False
        position = await run_in_threadpool(self._position)
        rows = await asyncio.wait_for(self.client.xread({self.channel: position}, count=1), self.timeout)
        if not rows or self._stop.is_set():
            return False
        stream_id, fields = rows[0][1][0]
        if isinstance(stream_id, bytes):
            stream_id = stream_id.decode('ascii')
        try:
            raw = fields.get(b'envelope', fields.get('envelope'))
            # Internal snapshots follow the write-side contract, which permits
            # large context/settings values. The client inbound frame cap does
            # not apply here: quarantining committed snapshots loses updates.
            if not isinstance(raw, (str, bytes)):
                raise ValueError('invalid envelope type')
            event = json.loads(raw)
            event_id = event.get('eventID') if isinstance(event, dict) else None
            if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 256:
                raise ValueError('event identity')
            project_event(event, event.get('workspaceID'))
        except (ValueError, UnicodeError, TypeError, RecursionError, ProjectionError):
            await run_in_threadpool(self._commit, stream_id, reason='invalid_or_unsupported_envelope')
            log.warning('Realtime entry quarantined: invalid_or_unsupported_envelope')
            return True
        seen = await run_in_threadpool(self._seen, event_id)
        if not seen:
            await asyncio.wait_for(self.hub.publish(event), self.timeout)
        await run_in_threadpool(self._commit, stream_id, event_id=None if seen else event_id)
        return True

    async def run(self):
        if self._running:
            raise RuntimeError('Consumer already running')
        self._running = True
        try:
            while not self._stop.is_set():
                try:
                    progressed = await self.tick()
                except (RedisError, OSError, asyncio.TimeoutError, DatabaseBusy):
                    log.warning('Realtime bridge unavailable; retrying')
                    progressed = False
                if not progressed:
                    try:
                        await asyncio.wait_for(self._stop.wait(), self.retry_delay)
                    except asyncio.TimeoutError:
                        pass
        finally:
            self._running = False
