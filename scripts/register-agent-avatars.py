"""Assign domain avatars to existing agents without touching their other settings."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from sqlalchemy import select
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.workspaces.models import workspaces
from workpal_backend.workspace_content.repository import list_records, put_record

ROOT=Path(__file__).resolve().parents[1]
LEGACY={'Product partner':'intent','Architecture partner':'design-role','Engineering partner':'implementation','Quality partner':'verifier'}

def main():
 settings=Settings()
 if not settings.dev_auth:raise RuntimeError('Local development authentication required')
 roles={r['id']:r for r in json.loads((ROOT/'apps/web/app/capabilities/data/role-profiles.json').read_text())}
 db=Database(settings)
 try:
  backup=str(db.engine.url.database)+'.before-agent-avatars-'+datetime.now().strftime('%Y%m%d%H%M%S%f')
  with sqlite3.connect(db.engine.url.database) as source,sqlite3.connect(backup) as target:source.backup(target)
  counts={}
  with db.transaction() as session:
   for ws in session.execute(select(workspaces)).mappings():
    count=0
    for agent in list_records(session,ws['id'],'agents'):
     role=(agent.get('metadata') or {}).get('catalog_role_id') or (agent['id'][9:] if agent['id'].startswith('workflow-') else LEGACY.get(agent['id']))
     if role not in roles:raise RuntimeError('No domain avatar mapped for '+agent['name'])
     url=roles[role]['avatarUrl']
     if not url.startswith('emoji:') or not url[6:].strip():raise RuntimeError('Native emoji avatar required')
     if agent.get('avatar_url')!=url:put_record(session,ws['id'],'agents',{**agent,'avatar_url':url})
     count+=1
    counts[ws['name']]=count
  print(json.dumps({'agents':counts,'backup':backup}))
 finally:db.close()
if __name__=='__main__':main()
