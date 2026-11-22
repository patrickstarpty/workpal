"""Replace TAP's roster with SMART's agents, remapping legacy references atomically."""
import copy
import json
import sqlite3
from datetime import datetime
from sqlalchemy import select
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.workspaces.models import workspaces
from workpal_backend.workspace_content.models import records
from workpal_backend.workspace_content.repository import list_records, put_record, delete_record

LEGACY={'Product partner':'workflow-intent','Architecture partner':'workflow-design-role',
        'Engineering partner':'workflow-implementation','Quality partner':'workflow-verifier'}


def sync(session):
 source=session.execute(select(workspaces).where(workspaces.c.slug=='workpal-team')).mappings().one()
 target=session.execute(select(workspaces).where(workspaces.c.slug=='review')).mappings().one()
 agents={a['id']:a for a in list_records(session,source['id'],'agents')}
 if len(agents)!=15 or not set(LEGACY.values())<=agents.keys():raise RuntimeError('Expected SMART role roster')
 current=list_records(session,target['id'],'agents')
 unknown={a['id'] for a in current}-agents.keys()-LEGACY.keys()
 if unknown:raise RuntimeError('Unmapped TAP agents: '+str(sorted(unknown)))
 def remap(value,key=''):
  if isinstance(value,dict):return {k:remap(v,k) for k,v in value.items()}
  if isinstance(value,list):return [remap(v,key) for v in value]
  if isinstance(value,str) and value in LEGACY:
   identity=LEGACY[value]
   return agents[identity]['name'] if key in ('agent','leader','agent_name','author_name','actor_name','assignee_name') else identity
  return value
 changed=[]
 for row in session.execute(select(records).where(records.c.workspace_id==target['id'],records.c.kind!='agents')).mappings():
  body=remap(row['body'])
  if body!=row['body']:
   put_record(session,target['id'],row['kind'],body);changed.append((row['kind'],row['id']))
 for agent in agents.values():
  body=copy.deepcopy(agent);body['workspace_id']=target['id']
  # Any embedded workspace-owned configuration must belong to the destination.
  def rebind(value):
   if isinstance(value,dict):return {k:(target['id'] if k=='workspace_id' else rebind(v)) for k,v in value.items()}
   if isinstance(value,list):return [rebind(v) for v in value]
   return value
  put_record(session,target['id'],'agents',rebind(body))
 removed=[]
 for old in current:
  if old['id'] not in agents:
   delete_record(session,target['id'],'agents',old['id']);removed.append(old['id'])
 assert {a['id'] for a in list_records(session,target['id'],'agents')}==agents.keys()
 return {'agents':len(agents),'removed':removed,'updated_references':changed}


def main():
 settings=Settings()
 if not settings.dev_auth:raise RuntimeError('Local development authentication required')
 db=Database(settings)
 try:
  backup=str(db.engine.url.database)+'.before-smart-to-tap-'+datetime.now().strftime('%Y%m%d%H%M%S%f')
  with sqlite3.connect(db.engine.url.database) as source,sqlite3.connect(backup) as target:source.backup(target)
  with db.transaction() as session:result=sync(session)
  print(json.dumps({**result,'backup':backup}))
 finally:db.close()
if __name__=='__main__':main()
