"""Exact-copy human publication permission, without sending capability.

Integrations must additionally verify the destination's current audience against
 data policy before sending. A valid identifier is not audience verification.
"""
import hashlib
from datetime import timedelta
from uuid import UUID
from django.core.exceptions import ValidationError
from django.utils import timezone
from workpal.contracts import Actor, ObjectRef, PublicationPayload, DomainError
from workpal.identity.service import require_member
from workpal.storage import atomic_write
from .models import ContentSnapshot, Publication
from .service import register_object, derive_scope, authorize, resolve, deny


def digest(body):
    return hashlib.sha256(bytes(body)).hexdigest()


def conflict():
    raise DomainError('revision_conflict', 'Publication changed.', status=409)


def store_content(workspace_id, ref, body, source_refs=()):
    if not isinstance(body, bytes) or len(body) > 1048576:
        raise DomainError('invalid_content', 'Content must be bytes up to 1 MiB.')
    content_hash = digest(body)
    def write():
        existing = ContentSnapshot.objects.filter(ref__kind=ref.kind, ref__object_id=ref.id).first()
        if existing and (bytes(existing.body) != body or existing.content_hash != content_hash):
            conflict()
        register_object(workspace_id, ref, source_refs)
        ContentSnapshot.objects.get_or_create(ref=resolve(ref), defaults={'body': body, 'content_hash': content_hash})
        return ref
    return atomic_write(write)


def refs(p):
    return {ObjectRef(o.kind, o.object_id) for o in p.sources.all()}


def checked(actor, payload_id):
    if not isinstance(payload_id, (str, UUID)):
        deny()
    try:
        p = Publication.objects.select_related('content__ref').get(pk=payload_id, workspace_id=actor.workspace_id)
    except (Publication.DoesNotExist, ValueError, ValidationError):
        deny()
    authorize(actor, 'read', refs(p) | {ObjectRef(p.content.ref.kind, p.content.ref.object_id)})
    return p


def payload(p):
    return PublicationPayload(str(p.pk), refs(p), p.destination, p.content_hash,
                              ObjectRef(p.content.ref.kind, p.content.ref.object_id), p.revision, p.status)


def binding(p):
    return dict(hash=digest(p.body), destination=p.destination, revision=p.revision,
                content=p.content_id, sources=sorted((r.kind, r.id) for r in refs(p)),
                creator=p.creator_id, approver=p.approver_id,
                approved_at=p.approved_at.isoformat() if p.approved_at else None,
                expires_at=p.expires_at.isoformat() if p.expires_at else None)


def valid_content(p):
    if digest(p.body) != p.content_hash or bytes(p.body) != bytes(p.content.body) or digest(p.content.body) != p.content.content_hash:
        deny()
    scope = derive_scope([ObjectRef(p.content.ref.kind, p.content.ref.object_id)] + list(refs(p)))
    if scope.source_refs != refs(p):
        deny()


def prepare_publication(actor, source_refs, destination, content_ref):
    if not isinstance(destination, str) or not destination.strip() or len(destination) > 255 or '://' in destination:
        raise DomainError('invalid_destination', 'Provide a stable destination identifier.')
    def write():
        all_refs = tuple(source_refs) + (content_ref,)
        authorize(actor, 'read', all_refs)
        scope = derive_scope(all_refs)
        content = ContentSnapshot.objects.filter(ref=resolve(content_ref)).first()
        if content is None or digest(content.body) != content.content_hash:
            deny()
        p = Publication.objects.create(workspace_id=actor.workspace_id, creator_id=actor.user_id,
            content=content, body=bytes(content.body), content_hash=digest(content.body), destination=destination)
        p.sources.set([resolve(r) for r in scope.source_refs])
        return payload(p)
    return atomic_write(write)


def read_publication(actor, payload_id):
    p = checked(actor, payload_id)
    valid_content(p)
    return payload(p)


def approve_publication(actor, payload_id, expected_revision, expected_hash, destination):
    if type(expected_revision) is not int or expected_revision < 1:
        raise DomainError('invalid_revision', 'Expected a positive integer revision.')
    def write():
        if actor.executor_id is not None:
            deny()
        p = checked(actor, payload_id)
        if p.revision != expected_revision:
            conflict()
        valid_content(p)
        if expected_hash != digest(p.body) or destination != p.destination:
            deny()
        require_member(Actor(p.creator_id, p.workspace_id), p.workspace_id)
        authorize(actor, 'publish', refs(p))
        p.revision += 1
        p.status = 'approved'
        p.approver_id = actor.user_id
        p.approved_at = timezone.now()
        p.expires_at = p.approved_at + timedelta(minutes=10)
        p.approval = binding(p)
        p.save()
        return payload(p)
    return atomic_write(write)


def authorize_publication(actor, payload_id, expected_hash):
    def check():
        p = checked(actor, payload_id)
        valid_content(p)
        if p.creator_id != actor.user_id or p.status != 'approved' or not p.expires_at or p.expires_at <= timezone.now() or expected_hash != digest(p.body):
            deny()
        # JSON stores tuples as lists.
        import json
        if p.approval != json.loads(json.dumps(binding(p))):
            deny()
        authorize(Actor(p.approver_id, p.workspace_id), 'publish', refs(p))
    return atomic_write(check)
