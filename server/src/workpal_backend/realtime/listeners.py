"""Original registerListeners personal and workspace dispatch on EventBus.

This synchronous boundary expects a synchronous broadcaster. The legacy outbox
bridge remains a separate pipeline until canonical application activation.
"""
from .event_payloads import InvitationResponse, MemberWithUserResponse, StringPointer, marshal_event_json
from .forwarding import PERSONAL_EVENTS, forward_workspace_event, project_outbound


def _string(value):
    return value if type(value) is str else ''


def register_listeners(bus, broadcaster, *, audience=None, metrics=None):
    def send(event, recipient, *, exclude=False):
        if not recipient:
            return
        try:
            data = marshal_event_json(dict(type=event.get('type', ''),
                payload=project_outbound(event.get('type', ''), event.get('payload')),
                actor_id=event.get('actorID', ''), actor_type=event.get('actorType', '')))
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return
        if metrics is not None:
            metrics.record_event(event.get('type', ''))
        if exclude:
            broadcaster.send_to_user(recipient, data, event.get('workspaceID', ''))
        else:
            broadcaster.send_to_user(recipient, data)

    def personal(event):
        kind = event.get('type', '')
        if kind in ('invitation:accepted', 'invitation:declined'):
            send(event, event.get('actorID', ''), exclude=True)
            return
        payload = event.get('payload')
        if type(payload) is not dict:
            return
        recipient = ''
        if kind in ('inbox:new', 'inbox:snoozed'):
            if kind == 'inbox:snoozed':
                recipient = _string(payload.get('recipient_id'))
            item = payload.get('item')
            if not recipient and type(item) is dict:
                recipient = _string(item.get('recipient_id'))
        elif kind == 'invitation:created':
            invitation = payload.get('invitation')
            if type(invitation) is InvitationResponse:
                recipient = invitation.invitee_user_id
            elif type(invitation) is dict:
                pointer = invitation.get('invitee_user_id')
                if type(pointer) is StringPointer:
                    recipient = str(pointer)
        elif kind == 'invitation:revoked':
            pointer = payload.get('invitee_user_id')
            if type(pointer) is StringPointer:
                recipient = str(pointer)
        elif kind == 'member:added':
            member = payload.get('member')
            if type(member) is MemberWithUserResponse:
                recipient = member.user_id
            elif type(member) is dict:
                recipient = _string(member.get('user_id'))
        else:
            recipient = _string(payload.get('recipient_id'))
        send(event, recipient, exclude=kind == 'member:added')

    for kind in sorted(PERSONAL_EVENTS | {'invitation:accepted', 'invitation:declined', 'member:added'}):
        bus.subscribe(kind, personal)
    bus.subscribe_all(lambda event: forward_workspace_event(event, broadcaster, audience=audience, metrics=metrics))
