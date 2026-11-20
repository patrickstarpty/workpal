"""SQLite upload drafts, verified artifacts and current source authorization."""
import re
from workpal.contracts import DomainError, ObjectRef
from workpal.access.service import authorize, register_object
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from .models import Upload, UploadChunk, Artifact, ArtifactBlob

MAX_SIZE = 25 * 1024 * 1024
MAX_CHUNK = 256 * 1024

def invalid():
    raise DomainError('invalid_input', 'Invalid upload fields.')

def text(value, limit):
    if type(value) is not str or not value or len(value) > limit: invalid()
    try: value.encode('utf-8')
    except UnicodeError: invalid()
    return value

def validate_metadata(value):
    if type(value) is not dict or set(value) - {'filename', 'media_type', 'size', 'source_refs'} or not {'filename', 'size'} <= set(value): invalid()
    filename = text(value['filename'], 255)
    if any(c in filename for c in '\0\r\n'): invalid()
    mime = text(value.get('media_type', 'application/octet-stream'), 127)
    if not re.fullmatch(r"[A-Za-z0-9!#$%&'*+.^_`|~-]+/[A-Za-z0-9!#$%&'*+.^_`|~-]+", mime): invalid()
    size = value['size']
    if type(size) is not int or not 0 <= size <= MAX_SIZE: invalid()
    sources = value.get('source_refs', [])
    if type(sources) is not list or len(sources) > 50: invalid()
    refs = []
    for source in sources:
        if type(source) is not dict or set(source) != {'kind', 'id'}: invalid()
        refs.append(ObjectRef(text(source['kind'], 100), text(source['id'], 255)))
    return dict(filename=filename, media_type=mime, size=size), refs

def ref(pk): return ObjectRef('artifact_upload', str(pk))
def view(u):
    return dict(id=u.pk, filename=u.filename, media_type=u.media_type, size=u.size,
                offset=u.received, status='completed' if u.artifact_id else 'open', artifact_id=u.artifact_id or 0, created_at=u.created_at.isoformat())

def selected(actor, upload_id, capability='read'):
    if type(upload_id) is not int or not 1 <= upload_id <= MAX_SQLITE_INTEGER: invalid()
    u = Upload.objects.filter(pk=upload_id, workspace_id=actor.workspace_id, owner_id=actor.user_id).first()
    if u is None: raise DomainError('not_found', 'Upload unavailable.', status=404)
    authorize(actor, capability, [ref(u.pk)])
    return u

def begin(actor, metadata):
    def write():
        fields, refs = validate_metadata(metadata)
        authorize(actor, 'write', refs)
        u = Upload.objects.create(workspace_id=actor.workspace_id, owner_id=actor.user_id, **fields)
        register_object(actor.workspace_id, ref(u.pk), refs)
        return view(u)
    return atomic_write(write)

def status(actor, upload_id): return view(selected(actor, upload_id))

def append(actor, upload_id, offset, chunk):
    if type(offset) is not int or offset < 0 or type(chunk) is not bytes or not chunk: invalid()
    if len(chunk) > MAX_CHUNK: raise DomainError('too_large', 'Chunk too large.', status=413)
    def write():
        u = selected(actor, upload_id, 'write')
        if u.artifact_id: raise DomainError('upload_closed', 'Upload closed.', status=409)
        old = UploadChunk.objects.filter(upload=u, offset=offset).first()
        if old is not None and bytes(old.bytes) == chunk: return u.received
        if old is not None or offset != u.received or offset + len(chunk) > u.size:
            raise DomainError('offset_conflict', 'Upload offset conflict.', status=409)
        if not Upload.objects.filter(pk=u.pk, received=offset).update(received=offset + len(chunk)):
            raise DomainError('offset_conflict', 'Upload offset conflict.', status=409)
        UploadChunk.objects.create(upload=u, offset=offset, bytes=chunk)
        return offset + len(chunk)
    return atomic_write(write)

def artifact_ref(pk): return ObjectRef('artifact', str(pk))

def read(actor, artifact_id):
    if type(artifact_id) is not int or not 1 <= artifact_id <= MAX_SQLITE_INTEGER: invalid()
    a = Artifact.objects.filter(pk=artifact_id, workspace_id=actor.workspace_id).values('id','filename','media_type','owner_id','created_at','blob__size','blob__sha256').first()
    if a is None: raise DomainError('not_found', 'Artifact unavailable.', status=404)
    authorize(actor, 'read', [artifact_ref(artifact_id)])
    return dict(id=a['id'], filename=a['filename'], media_type=a['media_type'], size=a['blob__size'], sha256=a['blob__sha256'], owner_user_id=a['owner_id'], created_at=a['created_at'].isoformat())

def read_chunk(actor, artifact_id, offset, length=MAX_CHUNK):
    from django.db.models import F, Func, Value, BinaryField
    a = read(actor, artifact_id)
    if type(offset) is not int or not 0 <= offset <= a['size'] or type(length) is not int or not 1 <= length <= MAX_CHUNK: invalid()
    if offset == a['size']: return b''
    return bytes(Artifact.objects.filter(pk=artifact_id).annotate(piece=Func(F('blob__content'), Value(offset+1), Value(length), function='substr', output_field=BinaryField())).values_list('piece', flat=True).get())

def finish(actor, upload_id, sha256):
    import hashlib
    if type(sha256) is not str or not re.fullmatch('[0-9a-f]{64}', sha256): invalid()
    def conflict(): raise DomainError('upload_conflict', 'Upload content conflict.', status=409)
    def write():
        u = selected(actor, upload_id, 'write')
        if u.artifact_id:
            a = read(actor, u.artifact_id)
            if a['sha256'] != sha256: conflict()
            return a
        if u.received != u.size or u.size > MAX_SIZE: conflict()
        parts, offset = [], 0
        for c in UploadChunk.objects.filter(upload=u).order_by('offset'):
            data = bytes(c.bytes)
            if c.offset != offset or not data: conflict()
            offset += len(data)
            if offset > u.size: conflict()
            parts.append(data)
        content = b''.join(parts)
        if offset != u.size or hashlib.sha256(content).hexdigest() != sha256: conflict()
        blob, created = ArtifactBlob.objects.get_or_create(workspace_id=u.workspace_id, sha256=sha256, size=u.size, defaults={'content':content})
        if not created and bytes(blob.content) != content: conflict()
        a = Artifact.objects.create(workspace_id=u.workspace_id, owner_id=u.owner_id, filename=u.filename, media_type=u.media_type, blob=blob)
        register_object(u.workspace_id, artifact_ref(a.pk), [ref(u.pk)])
        u.artifact = a
        u.save(update_fields=['artifact'])
        UploadChunk.objects.filter(upload=u).delete()
        return read(actor, a.pk)
    return atomic_write(write)
