"""Deterministic comparison of authorized immutable Delivery snapshots."""
from copy import deepcopy
from workpal.contracts import DomainError
from workpal.access.service import authorize
from workpal.identity.service import require_member
from . import service
from .models import Delivery


def resolve(actor, before_delivery_id, after_delivery_id):
    ids = (before_delivery_id, after_delivery_id)
    for pk in ids:
        service.issues.integer(pk)
    require_member(actor, actor.workspace_id)
    rows = {row['id']: row for row in Delivery.objects.filter(
        workspace_id=actor.workspace_id, pk__in=ids).values('id', 'subject_type', 'subject_id')}
    if any(pk not in rows for pk in ids):
        raise DomainError('not_found', 'Delivery unavailable.', status=404)
    refs = list(dict.fromkeys(service.ref(pk) for pk in ids))
    authorize(actor, 'read', refs)
    before, after = (rows[pk] for pk in ids)
    if (before['subject_type'], before['subject_id']) != (after['subject_type'], after['subject_id']):
        raise DomainError('conflict', 'Deliveries must share a subject.', status=409)
    return [service.issues.ref(int(before['subject_id']))] + refs


def _changes(before, after, key):
    old = {item[key]: item for item in before}
    new = {item[key]: item for item in after}
    return dict(added=[item for item in after if item[key] not in old],
        removed=[item for item in before if item[key] not in new],
        changed=[{key: item[key], 'before': old[item[key]], 'after': item}
                 for item in after if item[key] in old and old[item[key]] != item],
        before_order=list(old), after_order=list(new))


def compare(actor, before_delivery_id, after_delivery_id):
    resolve(actor, before_delivery_id, after_delivery_id)
    rows = {row.pk: service.view(row) for row in Delivery.objects.filter(
        workspace_id=actor.workspace_id, pk__in={before_delivery_id, after_delivery_id})}
    before, after = rows[before_delivery_id], rows[after_delivery_id]
    def header(item):
        return dict(id=item['id'], number=item['number'], sha256=item['sha256'],
            requirements_revision=item['requirements_snapshot']['number'],
            requirements_sha256=item['requirements_snapshot']['sha256'],
            workflow_sha256=item['workflow_snapshot']['sha256'])
    text = []
    for field in ('summary', 'limitations', 'requirements.title', 'requirements.description'):
        def value(item):
            return item['requirements_snapshot'][field.split('.')[1]] if '.' in field else item[field]
        if value(before) != value(after):
            text.append(dict(field=field, before=value(before), after=value(after)))
    return deepcopy(dict(subject=before['subject'], before=header(before), after=header(after),
        text_changes=text, criteria=_changes(before['requirements_snapshot']['criteria'], after['requirements_snapshot']['criteria'], 'key'),
        artifacts=_changes(before['artifacts_snapshot'], after['artifacts_snapshot'], 'id'),
        evidence=_changes(before['evidence'], after['evidence'], 'criterion_key'),
        workflow_changed=before['workflow_snapshot'] != after['workflow_snapshot']))
