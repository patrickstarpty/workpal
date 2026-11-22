"""Redis-only invitation admission, independent of SQLite transactions."""
from dataclasses import dataclass
from hashlib import sha256
import math
from uuid import uuid4

from redis.exceptions import RedisError
from workpal_backend.infrastructure.redis import RedisResources


@dataclass(frozen=True)
class WindowLimit:
    limit: int
    seconds: float

    def __post_init__(self):
        if isinstance(self.limit, bool) or not isinstance(self.limit, int) or self.limit < 1:
            raise ValueError('limit must be a positive integer')
        if not math.isfinite(self.seconds) or self.seconds <= 0:
            raise ValueError('window must be finite and positive')


class InvitationAdmissionError(Exception):
    """Map body directly to JSONResponse; do not wrap it in HTTPException.detail."""
    def __init__(self, status_code: int, body: dict[str, str | int], retry: int):
        super().__init__(body['error'])
        self.status_code = status_code
        self.body = body
        self.headers = {'Retry-After': str(retry), 'Cache-Control': 'no-store'}


_SCRIPT = """
local now
if ARGV[1] == '' then
    local t = redis.call('TIME')
    now = tonumber(t[1]) * 1000 + tonumber(t[2]) / 1000
else
    now = tonumber(ARGV[1])
end
-- Validate types before writes: Lua errors do not roll back earlier writes.
for i=1,3 do
    local kind = redis.call('TYPE', KEYS[i]).ok
    if kind ~= 'none' and kind ~= 'zset' then
        return redis.error_reply('invalid admission key type')
    end
end
local retry = 0
for i=1,3 do
    local window = tonumber(ARGV[2*i+2])
    local limit = tonumber(ARGV[2*i+1])
    redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', now-window)
    local count = redis.call('ZCARD', KEYS[i])
    if count >= limit then
        local oldest = redis.call('ZRANGE', KEYS[i], count-limit, count-limit, 'WITHSCORES')
        retry = math.max(retry, tonumber(oldest[2])+window-now)
    end
end
if retry > 0 then return math.max(1, math.ceil(retry/1000)) end
for i=1,3 do
    redis.call('ZADD', KEYS[i], now, ARGV[2])
    redis.call('PEXPIRE', KEYS[i], math.ceil(tonumber(ARGV[2*i+2])))
end
return 0
"""


class InvitationAdmission:
    def __init__(self, resources: RedisResources, *, limits: tuple[WindowLimit, ...] = (
        WindowLimit(10, 600), WindowLimit(50, 86400), WindowLimit(6, 86400),
    )):
        if len(limits) != 3:
            raise ValueError('actor, workspace and recipient limits required')
        self.resources = resources
        self.limits = limits

    def keys(self, actor_id: str, workspace_id: str, email: str) -> tuple[str, ...]:
        digest = sha256(email.strip().lower().encode('utf-8')).hexdigest()
        return tuple(self.resources.key(f'mul:invitation:{dimension}:{value}') for dimension, value in (
            ('actor', actor_id), ('workspace', workspace_id), ('recipient', digest)))

    async def admit(self, actor_id: str, workspace_id: str, email: str, *, now: float | None = None) -> None:
        """Call after auth, validation and duplicate preflight, before write BEGIN.

        Successful admission spends all budgets even if the later mutation fails.
        `now` is an internal test-only seconds clock; routes must never bind it to
        request input. Production defaults to Redis TIME inside the atomic script.
        """
        if now is not None and not math.isfinite(now):
            raise ValueError('now must be finite')
        args: list[str | float | int] = ['' if now is None else now * 1000, uuid4().hex]
        for limit in self.limits:
            args.extend((limit.limit, limit.seconds * 1000))
        try:
            retry = int(await self.resources.client.eval(_SCRIPT, 3, *self.keys(actor_id, workspace_id, email), *args))
        except (RedisError, OSError) as exc:
            raise InvitationAdmissionError(503, {
                'code': 'invitation_rate_limiter_unavailable',
                'error': 'invitation service temporarily unavailable',
            }, 5) from exc
        if retry:
            raise InvitationAdmissionError(429, {
                'code': 'invitation_rate_limited', 'error': 'too many invitation requests',
                'retry_after_seconds': retry,
            }, retry)
