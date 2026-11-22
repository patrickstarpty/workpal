"""Typed in-process payloads consumed by the original realtime listeners.

StringPointer preserves Go's *string type assertion. JSON persistence erases
this distinction, so decoded strings must not be automatically promoted.
"""
from dataclasses import dataclass, fields
from ..infrastructure.go_response import marshal_map_json


class StringPointer(str):
    pass


class _Response:
    omitted_when_empty = frozenset()


@dataclass
class InvitationResponse(_Response):
    id: str = ''
    workspace_id: str = ''
    inviter_id: str = ''
    invitee_email: str = ''
    invitee_user_id: str | None = None
    role: str = ''
    status: str = ''
    created_at: str = ''
    updated_at: str = ''
    expires_at: str = ''
    inviter_name: str = ''
    inviter_email: str = ''
    workspace_name: str = ''
    omitted_when_empty = frozenset({'inviter_name', 'inviter_email', 'workspace_name'})


@dataclass
class MemberWithUserResponse(_Response):
    id: str = ''
    workspace_id: str = ''
    user_id: str = ''
    role: str = ''
    created_at: str = ''
    name: str = ''
    email: str = ''
    avatar_url: str | None = None


def marshal_event_json(value):
    """Sort map keys but retain declared struct field order, as encoding/json."""
    active = set()
    def encode(item):
        if isinstance(item, (_Response, dict, list, tuple)):
            identity = id(item)
            if identity in active:
                raise ValueError('circular JSON value')
            active.add(identity)
            try:
                if isinstance(item, _Response):
                    pairs = [(f.name, getattr(item, f.name)) for f in fields(item)
                             if f.name not in item.omitted_when_empty or getattr(item, f.name) != '']
                elif isinstance(item, dict):
                    if any(not isinstance(key, str) for key in item):
                        raise TypeError('event map keys must be strings')
                    pairs = sorted(item.items())
                else:
                    return b'[' + b','.join(encode(child) for child in item) + b']'
                return b'{' + b','.join(marshal_map_json(key) + b':' + encode(child) for key, child in pairs) + b'}'
            finally:
                active.remove(identity)
        return marshal_map_json(item)
    return encode(value)
