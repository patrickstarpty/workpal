"""Redis PAT cache: failures fall back to authoritative database reads."""
import time
from redis import Redis
from redis.exceptions import RedisError


def call(settings, operation, token_hash, *args, **kwargs):
    key=settings.redis_key_prefix+'mul:auth:pat:'+token_hash
    try:
        with Redis.from_url(settings.redis_url,decode_responses=True,
            socket_connect_timeout=.25,socket_timeout=.25,retry_on_timeout=False) as client:
            return getattr(client,operation)(key,*args,**kwargs)
    except (RedisError,OSError):
        return None


def get(settings, token_hash):
    return call(settings,'get',token_hash)


def put(settings, token_hash, user_id, expires_at):
    ttl=600 if expires_at is None else min(600,expires_at-time.time())
    milliseconds=int(ttl*1000)
    if milliseconds>0:call(settings,'set',token_hash,user_id,px=milliseconds)


def invalidate(settings, token_hash):
    call(settings,'delete',token_hash)
