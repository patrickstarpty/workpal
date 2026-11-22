"""Store existing delivery documents in SQLite; preserve board state and original records."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.workspaces.models import workspaces, members
from workpal_backend.workspace_content.document_import import import_documents

root = Path(__file__).resolve().parents[1]
db = Database(Settings())
try:
    path = db.engine.url.database
    backup = path + '.before-document-import-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    with sqlite3.connect(path) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    with db.transaction() as session:
        total = 0
        for wid in session.scalars(select(workspaces.c.id)):
            owner = session.scalar(select(members.c.user_id).where(
                members.c.workspace_id == wid, members.c.role == 'owner'))
            if not owner:
                raise ValueError('Workspace has no owner for the requested document import')
            total += import_documents(session, wid, owner, root / 'apps/web/public')
    print('Imported documents:', total)
    print('Backup:', backup)
finally:
    db.close()
