"""Route a decoded relay envelope without blocking its Redis reader."""
from .relay_frame import inject_event_id


def deliver_envelope(hub, envelope, *, daemon_runtime=None, wecom_outbound=None):
    if not envelope.payload_json:
        return
    frame = inject_event_id(envelope.payload_json, envelope.event_id)
    if envelope.scope == 'daemon_runtime':
        if daemon_runtime is not None:
            daemon_runtime(envelope.scope_id, frame, envelope.event_id)
    elif envelope.scope == 'wecom_outbound':
        if wecom_outbound is not None:
            wecom_outbound(envelope.scope_id, frame, envelope.event_id)
    elif envelope.scope == 'global':
        hub.broadcast_all(frame, event_id=envelope.event_id)
    elif envelope.scope == 'user':
        hub.send_to_user(envelope.scope_id, frame, envelope.workspace_id, envelope.event_id)
    else:
        hub.broadcast_to_scope(envelope.scope, envelope.scope_id, frame, envelope.event_id)
