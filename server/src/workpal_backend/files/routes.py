"""Local image uploads backed by the existing fenced file ledger."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from workpal_backend.auth.dependencies import Principal, require_principal
from workpal_backend.workspaces import service
from workpal_backend.workspace_content.routes import execute
from . import repository
from .models import upload_intent
from .storage import LocalBlobStore, SizeLimitExceeded

router = APIRouter()
LIMIT = 5 * 1024 * 1024


def image_type(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'): return 'image/png'
    if data.startswith(b'\xff\xd8\xff'): return 'image/jpeg'
    if data[:6] in (b'GIF87a', b'GIF89a'): return 'image/gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP': return 'image/webp'
    raise HTTPException(415, 'Choose a PNG, JPEG, GIF or WebP image')


@router.post('/api/upload-file', status_code=201)
async def upload(request: Request, principal: Principal = Depends(require_principal)):
    # Bound the entire multipart request before its parser can spool it.
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > LIMIT + 65536: raise HTTPException(413, 'Image exceeds 5 MiB')
    request._body = bytes(data)
    async with request.form(max_files=1, max_fields=3) as form:
        file = form.get('file')
        if not hasattr(file, 'file'): raise HTTPException(400, 'Expected an image upload')
        if set(form) - {'file'}: raise HTTPException(501, 'Attachment association is unavailable')
        mime = image_type(await file.read(16))
        await file.seek(0)
        def save():
            root = request.app.state.settings.upload_dir
            root.mkdir(parents=True, exist_ok=True)
            store = LocalBlobStore(root)
            row = execute(request, principal, lambda session, workspace: repository.reserve_intent(
                session, {'owner_id': principal.user_id, 'workspace_id': workspace['id']},
                {'kind': 'avatar'}, store.new_key()))
            try:
                with store.create_staging(row['storage_key'], row['lease_token']) as staging:
                    size, digest = store.write_bounded(staging, file.file, LIMIT)
                store.sync_and_promote(row['storage_key'], row['lease_token'])
                def finish(session, workspace):
                    if workspace['id'] != row['workspace_id']: raise HTTPException(404, 'workspace not found')
                    repository.finalize_ready(session, row['id'], row['lease_token'],
                        {'size_bytes': size, 'sha256': digest, 'content_type': mime, 'filename': file.filename})
                execute(request, principal, finish)
            except SizeLimitExceeded as exc:
                raise HTTPException(413, 'Image exceeds 5 MiB') from exc
            url = '/api/files/' + row['id']
            return dict(id=row['id'], url=url, download_url=url, filename=file.filename, size=size, content_type=mime)
        return await run_in_threadpool(save)


@router.get('/api/files/{file_id}')
def read_image(file_id: str, request: Request, principal: Principal = Depends(require_principal)):
    with request.app.state.database.transaction() as session:
        row = session.execute(select(upload_intent).where(upload_intent.c.id == file_id, upload_intent.c.state == 'ready')).mappings().one_or_none()
        if not row: raise HTTPException(404, 'Image not found')
        try: service.require_workspace_access(session, principal, row['workspace_id'])
        except service.WorkspaceAccessError as exc: raise HTTPException(404, 'Image not found') from exc
        with LocalBlobStore(request.app.state.settings.upload_dir).open_ready(row['storage_key']) as image:
            return Response(image.read(), media_type=row['content_type'], headers={'X-Content-Type-Options':'nosniff', 'Cache-Control':'private, no-store'})
