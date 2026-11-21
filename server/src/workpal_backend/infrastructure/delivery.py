"""Bounded dispatch to a durable Python internal Redis Stream extension.

REDIS_KEY_PREFIX + events:stream stores an envelope field with stable eventID.
This is distinct from Go per-scope realtime streams. No trim or expiry is
applied: consumer lifecycle, deduplication and safe retention remain pending.
SQL delivered means Redis accepted XADD, not consumer business completion.
"""
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from redis.exceptions import RedisError
from .outbox import claim_batch, ack, retry


class OutboxDelivery:
    def __init__(self, settings):
        self.channel = settings.redis_key_prefix + 'events:stream'
        # Parse URL first, then override timeout/retry query options as well.
        self.client = Redis.from_url(settings.redis_url)
        self.client.connection_pool.connection_kwargs.update(
            socket_connect_timeout=.25, socket_timeout=.25,
            retry_on_timeout=False, retry=Retry(NoBackoff(), 0))

    def dispatch(self, database, *, should_stop=lambda: False, retry_delay=30):
        """Attempt at most one event per tick; never hold SQL across Redis I/O."""
        if not 0 <= retry_delay <= 86400:
            raise ValueError('Invalid retry delay')
        if should_stop():
            return 0
        with database.transaction() as session:
            rows = claim_batch(session, limit=1, lease_seconds=30)
        delivered = 0
        for row in rows:
            if should_stop():
                return delivered  # Durable lease expires after shutdown.
            try:
                self.client.xadd(self.channel, {'envelope': row['envelope']})
            except (RedisError, OSError):
                with database.transaction() as session:
                    retry(session, row['event_id'], row['claim_token'],
                          'Redis publication failed', delay_seconds=retry_delay)
            else:
                with database.transaction() as session:
                    delivered += ack(session, row['event_id'], row['claim_token'])
        return delivered

    def close(self):
        self.client.close()
