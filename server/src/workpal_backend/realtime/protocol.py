"""Go hub.go wire semantics, with private subscriptions denied until implemented."""
from copy import deepcopy
from dataclasses import dataclass
import json

MAX_FRAME_BYTES = 65536

@dataclass(frozen=True)
class FrameResult:
    reply: dict | None = None
    action: tuple[str, str, str] | None = None
    close_code: int | None = None


def parse_frame(raw: str | bytes, workspace_id: str, user_id: str) -> FrameResult:
    """Return reply and proposed hub operation; caller authenticates identity first.

    Oversize means close 1009, ignored input means an empty result. Unsubscribe
    mirrors Go: it removes an existing room without authorizing a new audience.
    No room operation is performed here. Task/chat subscribe always fails closed.
    """
    if len(raw.encode('utf-8') if isinstance(raw, str) else raw) > MAX_FRAME_BYTES:
        return FrameResult(close_code=1009)
    try:
        frame = json.loads(raw)
    except (ValueError, UnicodeError):
        return FrameResult()
    if not isinstance(frame, dict) or not isinstance(frame.get('type'), str):
        return FrameResult()
    kind = frame['type']
    if kind == 'ping':
        return FrameResult(reply={'type': 'pong'})
    if kind not in ('subscribe', 'unsubscribe'):
        return FrameResult()
    payload = frame.get('payload')
    scope = payload.get('scope') if isinstance(payload, dict) else None
    room = payload.get('id') if isinstance(payload, dict) else None
    valid = isinstance(scope, str) and isinstance(room, str) and scope != '' and room != ''
    scope = scope if isinstance(scope, str) else ''
    room = room if isinstance(room, str) else ''
    error = None
    if not valid:
        error = 'invalid payload'
    elif kind == 'subscribe':
        if scope in ('workspace', 'user'):
            if room != {'workspace': workspace_id, 'user': user_id}[scope]:
                error = 'forbidden'
        elif scope in ('task', 'chat'):
            error = 'forbidden'
        else:
            error = 'unknown_scope'
    response = {'scope': scope, 'id': room}
    if error:
        response['error'] = error
    return FrameResult(
        reply={'type': kind + ('_error' if error else '_ack'), 'payload': response},
        action=None if error else (kind, scope, room),
    )


class ProjectionError(ValueError):
    """Reject/quarantine this event; caller must never broadcast on failure."""


def project_event(event: dict, workspace_id: str) -> dict:
    """Project only a complete workspace response for the specified audience.

    Membership/session checks remain mandatory at the hub content-write boundary.
    Internal eventID is deliberately absent from browser frames.
    """
    allowed = {'eventID', 'type', 'workspaceID', 'actorID', 'actorType', 'payload'}
    if not isinstance(event, dict) or set(event) - allowed:
        raise ProjectionError('unsupported envelope fields or private audience hints')
    if event.get('type') in ('invitation:accepted', 'invitation:declined', 'member:added', 'member:updated'):
        return project_conclusion(event, workspace_id)
    if event.get('type') in ('invitation:created', 'invitation:revoked'):
        return project_invitation(event, workspace_id)
    if event.get('type') != 'workspace:updated':
        raise ProjectionError('unsupported event type')
    if not workspace_id or event.get('workspaceID') != workspace_id:
        raise ProjectionError('foreign workspace')
    if any(not isinstance(event.get(k), str) for k in ('actorID', 'actorType')):
        raise ProjectionError('invalid actor metadata')
    payload = event.get('payload')
    if not isinstance(payload, dict) or set(payload) != {'workspace'}:
        raise ProjectionError('invalid workspace payload')
    ws = payload['workspace']
    strings = {'id', 'name', 'slug', 'issue_prefix', 'created_at', 'updated_at'}
    nullable = {'description', 'context', 'avatar_url'}
    required = strings | nullable | {'settings', 'repos'}
    if not isinstance(ws, dict) or not required <= set(ws) or set(ws) - required - {'pinned_at'}:
        raise ProjectionError('incomplete or unknown workspace fields')
    if ws['id'] != workspace_id or any(not isinstance(ws[k], str) for k in strings):
        raise ProjectionError('invalid workspace identity or strings')
    if any(ws.get(k) is not None and not isinstance(ws[k], str) for k in nullable | {'pinned_at'}):
        raise ProjectionError('invalid nullable workspace strings')
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ProjectionError('non JSON workspace response') from exc
    return {'type': 'workspace:updated', 'payload': deepcopy(payload),
            'actor_id': event['actorID'], 'actor_type': event['actorType']}


def project_invitation(event, workspace_id):
    if not isinstance(workspace_id, str) or not workspace_id or event.get('workspaceID') != workspace_id:
        raise ProjectionError('foreign workspace')
    if any(not isinstance(event.get(k), str) for k in ('actorID', 'actorType')):
        raise ProjectionError('invalid actor metadata')
    payload = event.get('payload')
    if not isinstance(payload, dict):
        raise ProjectionError('invalid invitation payload')
    if event['type'] == 'invitation:created':
        if ('invitation' not in payload or set(payload) - {'invitation', 'workspace_name'}
                or not isinstance(payload['invitation'], dict)):
            raise ProjectionError('invalid invitation payload')
        if 'workspace_name' in payload and not isinstance(payload['workspace_name'], str):
            raise ProjectionError('invalid invitation workspace name')
        row = payload['invitation']
        strings = {'id', 'workspace_id', 'inviter_id', 'invitee_email', 'role', 'status', 'created_at', 'updated_at', 'expires_at'}
        optional = {'inviter_name', 'inviter_email', 'workspace_name'}
        if not strings | {'invitee_user_id'} <= set(row) or set(row) - strings - optional - {'invitee_user_id'}:
            raise ProjectionError('incomplete or unknown invitation fields')
        if row['workspace_id'] != workspace_id or row['role'] not in ('admin', 'member') or row['status'] != 'pending':
            raise ProjectionError('invalid invitation identity or state')
    else:
        row = payload
        strings = {'invitation_id', 'invitee_email'}
        optional = set()
        if set(row) != strings | {'invitee_user_id'}:
            raise ProjectionError('incomplete or unknown revocation fields')
    if any(not isinstance(row[k], str) or not row[k] for k in strings | (optional & set(row))):
        raise ProjectionError('invalid invitation strings')
    recipient = row['invitee_user_id']
    if recipient is not None and (not isinstance(recipient, str) or not recipient):
        raise ProjectionError('invalid invitation recipient')
    return dict(type=event['type'], payload=deepcopy(payload), actor_id=event['actorID'], actor_type=event['actorType'])


def resolve_audience(event):
    """Validate before resolving an explicit workspace or personal user room.

    A null invitee intentionally has no audience; never fall back to workspace.
    """
    project_event(event, event.get('workspaceID'))
    if event['type'] in ('invitation:accepted', 'invitation:declined', 'member:added'):
        recipient = event['payload']['member']['user_id'] if event['type'] == 'member:added' else event['actorID']
        return frozenset({('workspace', event['workspaceID'])} | ({('user', recipient)} if recipient else set()))
    if event['type'] in ('workspace:updated', 'member:updated'):
        return ('workspace', event['workspaceID'])
    row = event['payload']['invitation'] if event['type'] == 'invitation:created' else event['payload']
    recipient = row['invitee_user_id']
    return ('user', recipient) if recipient is not None else None


def project_conclusion(event, workspace_id):
    if not isinstance(workspace_id, str) or not workspace_id or event.get('workspaceID') != workspace_id:
        raise ProjectionError('foreign workspace')
    if any(not isinstance(event.get(k), str) for k in ('actorID', 'actorType')):
        raise ProjectionError('invalid actor metadata')
    payload = event.get('payload')
    kind = event['type']
    required = {'invitation_id', 'invitee_email'} if kind == 'invitation:declined' else ({'member'} if kind in ('member:added', 'member:updated') else {'invitation_id', 'member'})
    optional = {'workspace_name'} if kind == 'member:added' else set()
    if not isinstance(payload, dict) or not required <= set(payload) or set(payload) - required - optional:
        raise ProjectionError('invalid conclusion payload')
    for key in (required - {'member'}) | (optional & set(payload)):
        if not isinstance(payload[key], str):
            raise ProjectionError('invalid conclusion string')
    if 'member' in payload:
        member = payload['member']
        strings = {'id', 'workspace_id', 'user_id', 'role', 'created_at', 'name', 'email'}
        if not isinstance(member, dict) or set(member) != strings | {'avatar_url'}:
            raise ProjectionError('incomplete or unknown member fields')
        if any(not isinstance(member[k], str) for k in strings) or member['workspace_id'] != workspace_id or member['role'] not in ('owner', 'admin', 'member'):
            raise ProjectionError('invalid member')
        if member['avatar_url'] is not None and not isinstance(member['avatar_url'], str):
            raise ProjectionError('invalid avatar')
    return dict(type=kind, payload=deepcopy(payload), actor_id=event['actorID'], actor_type=event['actorType'])
