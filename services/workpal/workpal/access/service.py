"""Trusted internal object registration and current source authorization."""
from django.db import transaction
from workpal.contracts import ObjectRef, DataScope, DomainError
from workpal.identity.service import require_member
from .models import RegisteredObject, SourceLink, SourceGrant


def deny():
    raise DomainError("permission_denied", "Object unavailable or permission denied.", status=403)


def resolve(ref):
    obj = RegisteredObject.objects.filter(kind=ref.kind, object_id=ref.id).first()
    if obj is None or not obj.available:
        deny()
    return obj


def derive_scope(refs):
    refs = tuple(refs)
    if not refs:
        deny()
    roots, visiting, visited = set(), set(), set()
    workspace_id = resolve(refs[0]).workspace_id

    def visit(obj):
        if not obj.available or obj.workspace_id != workspace_id or obj.pk in visiting:
            deny()
        if obj.pk in visited:
            return
        visiting.add(obj.pk)
        if obj.is_source:
            roots.add(ObjectRef(obj.kind, obj.object_id))
        for source in obj.sources.all():
            visit(source)
        visiting.remove(obj.pk)
        visited.add(obj.pk)

    for ref in refs:
        visit(resolve(ref))
    return DataScope(workspace_id, roots)


@transaction.atomic
def register_object(workspace_id, ref, source_refs=(), is_source=False):
    """Internal business interface; provenance is append-only."""
    sources = [resolve(source) for source in source_refs]
    for source in sources:
        if source.workspace_id != workspace_id:
            deny()
        derive_scope([ObjectRef(source.kind, source.object_id)])
    obj, created = RegisteredObject.objects.get_or_create(
        kind=ref.kind, object_id=ref.id,
        defaults=dict(workspace_id=workspace_id, is_source=is_source))
    if obj.workspace_id != workspace_id or not obj.available or (obj.is_source and not is_source):
        deny()
    if is_source and not obj.is_source:
        obj.is_source = True
        obj.save(update_fields=["is_source"])
    for source in sources:
        SourceLink.objects.get_or_create(derived=obj, source=source)
    derive_scope([ref])
    return ref


def authorize(actor, action, refs=()):
    if action not in {"read", "write", "publish"}:
        deny()
    require_member(actor, actor.workspace_id)
    refs = tuple(refs)
    if not refs:
        return
    scope = derive_scope(refs)
    if scope.workspace_id != actor.workspace_id:
        deny()
    for ref in scope.source_refs:
        grant = SourceGrant.objects.filter(user_id=actor.user_id, source=resolve(ref), read=True).first()
        if grant is None or not getattr(grant, action):
            deny()

def store_content(*args, **kwargs):
    from .publication import store_content as implementation
    return implementation(*args, **kwargs)

def prepare_publication(*args, **kwargs):
    from .publication import prepare_publication as implementation
    return implementation(*args, **kwargs)

def read_publication(*args, **kwargs):
    from .publication import read_publication as implementation
    return implementation(*args, **kwargs)

def approve_publication(*args, **kwargs):
    from .publication import approve_publication as implementation
    return implementation(*args, **kwargs)

def authorize_publication(*args, **kwargs):
    from .publication import authorize_publication as implementation
    return implementation(*args, **kwargs)
