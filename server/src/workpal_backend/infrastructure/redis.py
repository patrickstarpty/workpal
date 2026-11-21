from redis.asyncio import Redis
from redis.exceptions import RedisError
class RedisResources:
    def __init__(self, settings):
        self.prefix = settings.redis_key_prefix
        self.client = Redis.from_url(settings.redis_url, socket_connect_timeout=.25, socket_timeout=.25, retry_on_timeout=False)
    def key(self, suffix): return self.prefix + suffix
    async def ready(self):
        try: return bool(await self.client.ping())
        except (RedisError, OSError): return False
    async def close(self): await self.client.aclose()
