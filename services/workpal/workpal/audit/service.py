from .models import AuditEvent, Outbox


def record(actor, spec, result, payload, refs, scope_refs):
    # An allowlist mistake must not turn credential inputs into audit content.
    secret_markers = ('password', 'token', 'secret', 'apikey', 'authorization',
                      'credential', 'cookie', 'privatekey')
    safe = {
        key: payload[key] for key in spec.audit_fields if key in payload
        and not any(marker in key.lower().replace('_', '').replace('-', '')
                    for marker in secret_markers)
    }
    event = AuditEvent.objects.create(
        workspace_id=actor.workspace_id, actor_id=actor.user_id,
        action_id=spec.action_id, outcome=result.state,
        object_refs=refs, scope_refs=scope_refs, fields=safe,
    )
    if spec.mutating:
        Outbox.objects.create(
            event=event, workspace_id=actor.workspace_id,
            action_id=spec.action_id, object_refs=refs, scope_refs=scope_refs,
        )
