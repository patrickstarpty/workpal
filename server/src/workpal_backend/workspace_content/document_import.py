"""Import existing document bytes without reviving authored execution history."""
import base64
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit, unquote
from uuid import uuid4
from . import repository as repo


def import_documents(session, workspace_id, actor_id, public_root):
    count = 0
    root = Path(public_root).resolve()
    for attachment in repo.list_records(session, workspace_id, 'attachments'):
        if attachment.get('document_imported_at'):
            continue
        aid = attachment['id']
        content = repo.get_record(session, workspace_id, 'attachment_contents', aid)
        if content and isinstance(content.get('text'), str):
            data = content['text'].encode()
            stored = {'id': aid, 'text': content['text']}
        elif content and content.get('encoding') == 'base64':
            data = base64.b64decode(content['data'], validate=True)
            stored = {'id': aid, 'encoding': 'base64', 'data': content['data']}
        else:
            url = urlsplit(attachment.get('url', ''))
            if url.scheme or url.netloc or not url.path.startswith('/delivery/'):
                raise ValueError('Missing document content: ' + aid)
            path = (root / unquote(url.path).lstrip('/')).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError('Missing local document: ' + aid)
            data = path.read_bytes()
            stored = {'id': aid, 'encoding': 'base64', 'data': base64.b64encode(data).decode()}
        now = datetime.now(timezone.utc).isoformat()
        archived = bool(attachment.get('_fixture') or attachment.get('fixture_source'))
        repo.put_record(session, workspace_id, 'archived_attachments', attachment)
        updated = {key: value for key, value in attachment.items()
                   if key not in ('_fixture', 'fixture_source', 'source_task_id')}
        updated.update(url='/api/attachments/' + aid + '/content',
                       download_url='/api/attachments/' + aid + '/download',
                       attachment_download_url='/api/attachments/' + aid + '/download',
                       authenticated_download=True, size_bytes=len(data),
                       sha256=sha256(data).hexdigest(), document_imported_at=now)
        if archived:
            cid = str(uuid4())
            updated.update(comment_id=cid, uploader_type='member', uploader_id=actor_id)
            repo.put_record(session, workspace_id, 'comments', {
                'id': cid, 'workspace_id': workspace_id, 'issue_id': attachment['issue_id'],
                'type': 'comment', 'author_type': 'member', 'author_id': actor_id,
                'content': 'Document imported · ' + attachment['filename'],
                'created_at': now, 'updated_at': now, 'attachments': [updated],
            })
        else:
            # Existing real submissions keep their original author and timestamp.
            comment = repo.get_record(session, workspace_id, 'comments', attachment.get('comment_id'))
            if comment:
                comment = {**comment, 'attachments': [
                    updated if item.get('id') == aid else item for item in comment.get('attachments', [])]}
                repo.put_record(session, workspace_id, 'comments', comment)
        repo.put_record(session, workspace_id, 'attachments', updated)
        repo.put_record(session, workspace_id, 'attachment_contents', stored)
        count += 1
    return count
