"""Go SubscribeAll forwarding policy, independent of hub and audience queries.

Not yet wired to the legacy stream consumer. The injected audience resolver must
implement the Go private-project lookup and its two-second context deadline.
Personal event subscribers are separate and are intentionally skipped here.
"""
import logging
from .event_payloads import marshal_event_json

log=logging.getLogger(__name__)
PERSONAL_EVENTS=frozenset({
    'inbox:new','inbox:read','inbox:archived','inbox:unarchived','inbox:deleted',
    'inbox:batch-read','inbox:batch-archived','inbox:snoozed','inbox:unsnoozed',
    'invitation:created','invitation:revoked','issue_unread:changed',
})
MEMBER_PRIVATE_EVENTS=frozenset({'issue_view_preference:changed','pin:created','pin:deleted','pin:reordered'})
INTERNAL_KEYS={'issue:updated':('prev_description','prev_title'),'task:failed':('error',)}


def project_outbound(event_type,payload):
    keys=INTERNAL_KEYS.get(event_type)
    if not keys or not isinstance(payload,dict): return payload
    return {key:value for key,value in payload.items() if key not in keys}


def forward_workspace_event(event,broadcaster,*,audience=None,metrics=None):
    """Forward the global listener portion; audience errors never widen routing.

    Broadcaster errors propagate to EventBus's per-listener isolation. The
    callback returns (recipients, private); duplicate recipients are preserved.
    """
    kind=event.get('type','')
    def record():
        if metrics is not None:
            metrics.record_event(kind)
    if kind in PERSONAL_EVENTS: return
    workspace=event.get('workspaceID','')
    owner=event.get('chatSessionOwnerID','')
    chat_private=kind.startswith('chat:') or (kind=='task:message' and bool(event.get('chatSessionID','')))
    if chat_private and (not owner or not workspace): return
    frame=dict(type=kind,payload=project_outbound(kind,event.get('payload')),
               actor_id=event.get('actorID',''),actor_type=event.get('actorType',''))
    try:
        data=marshal_event_json(frame)
    except (ValueError,TypeError,UnicodeError,RecursionError):
        log.warning('Realtime event serialization failed: %s',kind)
        return
    if chat_private:
        record()
        broadcaster.broadcast_to_scope('workspace_member',workspace+':'+owner,data)
        return
    member=event.get('memberPrivateUserID','')
    if member or kind in MEMBER_PRIVATE_EVENTS:
        if member and workspace:
            record()
            broadcaster.broadcast_to_scope('workspace_member',workspace+':'+member,data)
        return
    if audience is not None and workspace:
        try: recipients,private=audience(event)
        except Exception:
            log.warning('Realtime audience resolution failed: %s',kind)
            return
        if private:
            record()
            for recipient in recipients or ():
                broadcaster.broadcast_to_scope('workspace_member',workspace+':'+recipient,data)
            return
    if workspace:
        record()
        broadcaster.broadcast_to_workspace(workspace,data)
    elif kind.startswith('daemon:'):
        record()
        broadcaster.broadcast(data)
