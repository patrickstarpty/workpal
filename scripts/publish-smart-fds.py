"""Attach user-authorized sample DOCX designs to their originating SMART Activity."""
import json,sqlite3,hashlib
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import select
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.workspaces.models import workspaces
from workpal_backend.workspace_content import repository as repo
ROOT=Path(__file__).resolve().parents[1]
TARGETS={2:'deliverable-1',8:'progress',14:'progress',20:'progress',7:'design-decision',15:'design-decision'}
db=Database(Settings())
try:
 backup=str(db.engine.url.database)+'.before-tds-'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
 with sqlite3.connect(db.engine.url.database) as source,sqlite3.connect(backup) as target:source.backup(target)
 result=[]
 with db.transaction() as s:
  ws=s.execute(select(workspaces).where(workspaces.c.slug=='workpal-team')).mappings().one();wid=ws['id']
  for number,suffix in TARGETS.items():
   iid=f'workflow-work-{number:02d}';cid='smart-activity-v1-'+iid+'-'+suffix
   comment=repo.get_record(s,wid,'comments',cid)
   if not comment:raise RuntimeError('Missing origin '+cid)
   filename=f'FDS-SMART-{number}.docx';data=(ROOT/'apps/web/public/delivery/fds'/filename).read_bytes();aid=f'smart-tds-v1-{number}';url='/delivery/fds/'+filename
   existing=repo.get_record(s,wid,'attachments',aid)
   if existing:
    if existing.get('sha256')!=hashlib.sha256(data).hexdigest():raise RuntimeError('Existing revision changed')
   else:
    attachment={'id':aid,'workspace_id':wid,'issue_id':iid,'comment_id':cid,'source_task_id':comment.get('source_task_id'),'filename':filename,'url':url,'download_url':url,'attachment_download_url':url,'content_type':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','size_bytes':len(data),'created_at':datetime.now(timezone.utc).isoformat(),'uploader_type':comment['author_type'],'uploader_id':comment['author_id'],'sha256':hashlib.sha256(data).hexdigest(),'revision':1,'_fixture':{'provenance':'user_authorized_sample_deliverable','execution':'none'}}
    repo.put_record(s,wid,'attachments',attachment)
    comment['attachments']=[*comment.get('attachments',[]),attachment]
    repo.put_record(s,wid,'comments',comment)
   result.append({'ticket':f'SMART-{number}','activity_id':cid,'run_id':comment.get('source_task_id'),'attachment_id':aid,'filename':filename,'sha256':hashlib.sha256(data).hexdigest()})
 (ROOT/'docs/handoffs/smart-fds-publication.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'attached':len(result),'backup':backup}))
finally:db.close()
