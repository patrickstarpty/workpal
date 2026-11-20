"""Persistent action approval; callers must resend inputs, never stored here."""
from datetime import timedelta
from uuid import UUID
from django.utils import timezone
from workpal.contracts import ActionResult, DomainError
from .models import Confirmation


def reject():
    raise DomainError('confirmation_conflict', 'Confirmation invalid or expired; prepare with a new key.', status=409)


def human(actor):
    if actor.executor_id is not None:
        raise DomainError('permission_denied', 'Human confirmation required.', status=403)


def check(actor, request, scope, digest, refs):
    try:
        token = UUID(str(request.confirmation_id))
    except (ValueError, TypeError, AttributeError):
        reject()
    row = Confirmation.objects.filter(pk=token, **scope).first()
    if row is None or row.request_hash != digest or row.expected_revision != request.expected_revision or row.scope_refs != refs:
        reject()
    return row


def prepare(request, scope, digest, refs):
    row, _ = Confirmation.objects.get_or_create(**scope, defaults={
        'request_hash': digest, 'expected_revision': request.expected_revision,
        'scope_refs': refs, 'expires_at': timezone.now() + timedelta(minutes=10)})
    if row.request_hash != digest or row.expected_revision != request.expected_revision or row.scope_refs != refs or row.consumed or row.expires_at <= timezone.now():
        reject()
    return ActionResult('waiting_confirmation', [], {
        'confirmation_id': str(row.pk), 'action_id': row.action_id,
        'expires_at': row.expires_at.isoformat(), 'request_hash': row.request_hash,
        'expected_revision': row.expected_revision})
