"""Caller-owned Redis cache of membership existence, never authorization roles."""
from asyncio import CancelledError
import logging

_log = logging.getLogger(__name__)
MEMBERSHIP_CACHE_TTL = 300


def _key(user_id: str, workspace_id: str) -> str:
    return 'mul:auth:member:' + user_id + ':' + workspace_id


class MembershipCache:
    def __init__(self, client=None):
        self._client = client

    def get(self, user_id: str, workspace_id: str) -> bool:
        if self._client is None:
            return False
        try:
            return self._client.get(_key(user_id, workspace_id)) is not None
        except (Exception, CancelledError) as error:
            _log.warning('membership_cache: get failed; falling back to DB: %s', error)
            return False

    def set(self, user_id: str, workspace_id: str) -> None:
        if self._client is None:
            return
        try:
            self._client.set(_key(user_id, workspace_id), '1', ex=MEMBERSHIP_CACHE_TTL)
        except (Exception, CancelledError) as error:
            _log.warning('membership_cache: set failed: %s', error)

    def invalidate(self, user_id: str, workspace_id: str) -> None:
        if self._client is None:
            return
        try:
            self._client.delete(_key(user_id, workspace_id))
        except (Exception, CancelledError) as error:
            _log.warning('membership_cache: invalidate failed: %s', error)
