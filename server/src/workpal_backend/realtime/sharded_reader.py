"""One fixed-shard XREAD loop with bounded replay and generation resets."""
import asyncio
import logging
import time

from .relay_consumer import _operation, _Stopped
from .relay_envelope import envelope_from_values
from .relay_metrics import RedisMetrics
from .sharded_config import sharded_stream_key, signed_duration
from .stream_retention import SECOND
from .redis_client import read_with_context

log = logging.getLogger(__name__)


def stream_start_id(now_ns, horizon_ns):
    milliseconds = (now_ns + signed_duration(-horizon_ns)) // 1_000_000
    return f'{max(0, milliseconds)}-0'


class ShardReader:
    def __init__(self, client, shard, config, deliver, *, metrics=None,
                 clock_ns=time.time_ns, generation=lambda: 0, is_stopping=lambda: False):
        self.client = client
        self.shard = shard
        self.config = config
        self.deliver = deliver
        self.metrics = metrics if metrics is not None else RedisMetrics()
        self.clock_ns = clock_ns
        self.generation = generation
        self.is_stopping = is_stopping
        self.stream = sharded_stream_key(shard)
        self.last_id = ''

    async def run(self, stop):
        self.last_id = stream_start_id(self.clock_ns(), self.config.replay_ns)
        generation = self.generation()
        while not stop.is_set() and not self.is_stopping():
            current = self.generation()
            if current != generation:
                self.last_id = stream_start_id(self.clock_ns(), self.config.replay_ns)
                generation = current
            if not await self.read_once(stop):
                return

    async def read_once(self, stop):
        try:
            result = await read_with_context(self.client, 'xread', stop,
                signed_duration(self.config.read_block_ns + SECOND) / SECOND,
                streams={self.stream: self.last_id}, count=self.config.read_count,
                block=max(1, self.config.read_block_ns // 1_000_000))
        except (_Stopped, TimeoutError):
            return True
        except Exception as error:
            self.metrics.xread_errors += 1
            self.metrics.last_error = str(error)
            log.warning('realtime/sharded-redis: XREAD failed: %s', error)
            try:
                await asyncio.wait_for(stop.wait(), 1)
                return False
            except TimeoutError:
                return True
        for _, messages in result or ():
            for message_id, values in messages:
                self.last_id = message_id.decode('utf-8', errors='surrogateescape') if isinstance(message_id, bytes) else message_id
                self.metrics.xread_total += 1
                envelope, valid = envelope_from_values(values)
                if valid and envelope.scope and envelope.scope_id:
                    self.deliver(envelope)
        return True
