"""Direct publisher sink acceptance; no browser or real WebSocket acceptance."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import select
from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.infrastructure.redis import RedisResources
from workpal_backend.realtime.consumer import RealtimeConsumer, quarantine


def test_restart_duplicate_poison_crash(settings, isolated_relay_redis_port):
    async def exercise():
        settings.redis_url = f'redis://127.0.0.1:{isolated_relay_redis_port}'
        settings.redis_key_prefix = 'test:consumer:' + uuid4().hex + ':'
        migrate(settings)
        db = Database(settings)
        resources = RedisResources(settings)
        frames = []
        class Sink:
            async def publish(self, event): frames.append(event)
        consumer = RealtimeConsumer(db, resources, Sink())
        event = json.loads((Path(__file__).parents[1]/'contracts/batches/realtime.json').read_text())['internal_event']
        event['eventID'] = 'stable'
        try:
            await resources.client.xadd(consumer.channel, {'envelope': json.dumps(event)})
            original = consumer._commit
            def crash(*args, **kwargs): raise RuntimeError('injected crash')
            consumer._commit = crash
            with pytest.raises(RuntimeError): await consumer.tick()
            consumer = RealtimeConsumer(db, resources, Sink())
            assert await consumer.tick()
            assert len(frames) == 2
            await resources.client.xadd(consumer.channel, {'envelope': json.dumps(event)})
            assert await consumer.tick()
            assert len(frames) == 2
            await resources.client.xadd(consumer.channel, {'envelope': 'bad'})
            assert await consumer.tick()
            with db.transaction() as s:
                assert s.execute(select(quarantine)).first()
            assert await resources.client.xlen(consumer.channel) == 3
            assert not await consumer.tick()
            task = asyncio.create_task(consumer.run())
            await asyncio.sleep(.01)
            consumer.stop()
            await asyncio.wait_for(task, 2)
        finally:
            await resources.client.delete(consumer.channel)
            await resources.close()
            db.close()
    asyncio.run(exercise())


@pytest.mark.parametrize('context', [None, 'x' * 70000, '中文' * 70000])
def test_authorized_delivery_and_failed_fanout(settings, context, isolated_relay_redis_port):
    from workpal_backend.auth.service import get_or_create_development_user
    from workpal_backend.workspaces import service
    from workpal_backend.infrastructure.delivery import OutboxDelivery
    from workpal_backend.realtime.protocol import project_event
    async def exercise():
        settings.redis_url = f'redis://127.0.0.1:{isolated_relay_redis_port}'
        settings.redis_key_prefix = 'test:consumer:' + uuid4().hex + ':'
        migrate(settings)
        db = Database(settings)
        resources = RedisResources(settings)
        delivery = OutboxDelivery(settings)
        frames = []
        class Sink:
            fail = True
            async def publish(self, event):
                if self.fail: raise RuntimeError('fanout failed')
                frames.append(project_event(event, event['workspaceID']))
        sink = Sink()
        consumer = RealtimeConsumer(db, resources, sink)
        try:
            with db.transaction() as s:
                uid = get_or_create_development_user(s, 'dev@workpal.local')['id']
                ws = service.create_workspace(s, uid, 'Original', 'bridge-test')
                result = service.update_workspace(s, {'identity_kind':'session','user_id':uid}, ws['id'], {'name':'Updated', 'context':context})
            assert delivery.dispatch(db) == 1
            with pytest.raises(RuntimeError): await consumer.tick()
            assert consumer._position() == '0-0'
            sink.fail = False
            assert await consumer.tick()
            assert frames == [{'type':'workspace:updated','payload':{'workspace':result},'actor_id':uid,'actor_type':'member'}]
            with db.transaction() as s:
                result = service.update_workspace(s, {'identity_kind':'session','user_id':uid}, ws['id'], {'name':'Again'})
            assert delivery.dispatch(db) == 1
            assert await consumer.tick()
            assert frames[-1]['payload']['workspace'] == result
            assert len(frames) == 2
            with db.transaction() as s:
                assert not s.execute(select(quarantine)).first()
        finally:
            await resources.client.delete(consumer.channel)
            delivery.close()
            await resources.close()
            db.close()
    asyncio.run(exercise())


def test_outage_stop(settings):
    async def exercise():
        migrate(settings)
        db = Database(settings)
        resources = RedisResources(settings)
        consumer = RealtimeConsumer(db, resources, object(), timeout=.1)
        try:
            task = asyncio.create_task(consumer.run())
            await asyncio.sleep(.15)
            consumer.stop()
            await asyncio.wait_for(task, .5)
            assert consumer._position() == '0-0'
        finally:
            await resources.close()
            db.close()
    asyncio.run(exercise())


def test_database_contention_does_not_kill_consumer(settings):
    from workpal_backend.infrastructure.database import DatabaseBusy
    async def exercise():
        migrate(settings)
        db = Database(settings)
        resources = RedisResources(settings)
        consumer = RealtimeConsumer(db, resources, object(), retry_delay=.01)
        attempts = []
        async def busy_tick():
            attempts.append(1)
            if len(attempts) == 1:
                raise DatabaseBusy('locked')
            consumer.stop()
            return False
        consumer.tick = busy_tick
        try:
            await asyncio.wait_for(consumer.run(), 1)
            assert len(attempts) == 2
        finally:
            await resources.close()
            db.close()
    asyncio.run(exercise())
