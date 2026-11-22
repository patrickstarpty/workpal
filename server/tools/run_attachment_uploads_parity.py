"""Actual Go UploadFile versus Python service through isolated query/transaction/storage fixtures."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.mutations import AttachmentMutations
from workpal_backend.files.upload_bindings import UploadBindings
from workpal_backend.files.write_transactions import AttachmentWriter
from workpal_backend.files.metadata import AttachmentMetadata
from workpal_backend.projects.access import Hidden
from workpal_backend.files.events import AttachmentEvents
from workpal_backend.comments.groups import CommentGroups
from workpal_backend.comments.projection import comment_response
from workpal_backend.infrastructure.query_errors import NoRows
from workpal_backend.auth.wakeup_actor import capture_wakeup_actor
from workpal_backend.infrastructure.go_uuid import parse_uuid
W='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
U='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
I='cccccccc-cccc-cccc-cccc-cccccccccccc'
C='dddddddd-dddd-dddd-dddd-dddddddddddd'
class Queries:
    def __init__(self,f):self.f=f;self.calls=[];self.created=None
    def record(self,kind,*args):
        self.calls.append([kind,*args]);failure=self.f['Failure']
        if failure==kind:raise RuntimeError(kind+' failed')
        if failure==kind+'-missing':raise NoRows()
        if failure==kind+'-cancel':raise asyncio.CancelledError()
    def task_row(self):
        return {field:parse_uuid(self.f[key]) if self.f.get(key) else None for field,key in [('id','Task'),('agent_id','TaskAgent'),('chat_session_id','TaskSession')]}
    def get_task(self,identity):self.record('source_task',identity);return self.task_row()
    def get_task_in_workspace(self,identity,workspace):self.record('upload_task',identity,workspace);return self.task_row()
    def session_row(self):return dict(id=self.f['Session'],workspace_id=self.f['Workspace'],agent_id=self.f['TaskAgent'],creator_id=self.f['Creator'])
    def get_chat_session_in_workspace(self,identity,workspace):self.record('session',identity,workspace);return self.session_row()
    def get_public_chat_session_in_workspace(self,identity,workspace):self.record('public_session',identity,workspace);return self.session_row()
    def get_agent(self,identity):self.record('agent',identity);return dict(id=self.f['TaskAgent'],workspace_id=self.f['Workspace'],owner_id=self.f['User'])
    def get_member(self,workspace,user):self.record('member',workspace,user);return dict(role='member')
    def get_issue_in_workspace(self,identity,workspace):self.record('issue',identity,workspace);return dict(id=I,workspace_id=W,project_id=None)
    def get_comment(self,identity):self.record('comment',identity);return dict(id=C,workspace_id=self.f['Workspace'].lower(),issue_id=I,deleted_at=None)
    def hidden(self,workspace):self.record('private',workspace);return Hidden()
    def lock_live_comment(self,identity,workspace):self.record('lock',identity,workspace)
    def create_attachment(self,params):
        fields=['id','workspace_id','uploader_type','uploader_id','filename','url','content_type','size_bytes','issue_id','comment_id','chat_session_id','task_id','source_context_id','width','height']
        self.record('create',*[params.get(field) for field in fields])
        self.created=dict(params,created_at=None,issue_revision=5 if self.f.get('Revisions') and params.get('issue_id') else 0,comment_revision=6 if self.f.get('Revisions') and params.get('comment_id') else 0)
        return self.created
    def get_comment_in_workspace(self,identity,workspace):
        self.record('comment_event',identity,workspace)
        return dict(id=C,workspace_id=workspace,issue_id=I,author_type='member',author_id=self.f['User'],content='body',type='text',revision=6,created_at=None,updated_at=None)
    def list_reactions_by_comment_ids(self,ids):
        self.record('reactions',ids)
        return [dict(id=I,comment_id=C,workspace_id=self.f['Workspace'],actor_type='member',actor_id=self.f['User'],emoji='ok',created_at=None)]
    def list_attachments_by_comment_ids(self,ids,workspace):
        self.record('attachments',ids,workspace)
        return [self.created]
class Tx:
    def __init__(self,q):self.q=q
    def execute(self,sql,args):self.q.record('execute',sql,*args)
    def commit(self):self.q.record('commit')
    def rollback(self):self.q.record('rollback')
class Storage:
    is_local=False
    def __init__(self,q):self.q=q
    def upload(self,key,data,media,name):self.q.record('upload',key,hashlib.sha256(data).hexdigest(),media,name);return 'https://storage/object'
    def key_from_url(self,url):return 'object'
    def delete_keys(self,keys):self.q.record('delete',keys)
    def cdn_domain(self):return ''
async def evaluate(f,observed_id):
    q=Queries(f);storage=Storage(q) if f['Storage'] else None
    def begin():q.record('begin');return Tx(q)
    parent=lambda:asyncio.CancelledError() if f['Cancelled'] else None
    metadata=AttachmentMetadata(storage)
    service=AttachmentMutations(q,begin,lambda tx:q,storage,metadata,lambda *args:q.record('publish',*args),
        user_id=f['User'],workspace_id=f['Workspace'],hidden_projects=q.hidden,request_error=parent,
        actor_source=f.get('Source',''),agent_id=f.get('Agent',''),task_id=f.get('Task',''),
        stable=f['Stable'],new_id=lambda:observed_id or I)
    response=await service.upload(base64.b64decode(f['Body']),f['ContentType'],raw_query=f['Query'].encode())
    return dict(status=response.status_code,body=json.loads(response.body) if response.body else None,calls=q.calls,generated_id=observed_id)

def multipart(fields=(),filename='example.SVG',data=b'<svg/>'):
    body=b'--b\r\nContent-Disposition: form-data; name="file"; filename="'+filename.encode()+b'"\r\nContent-Type: application/evil\r\n\r\n'+data+b'\r\n'
    for key,value in fields:body+=b'--b\r\nContent-Disposition: form-data; name="'+key.encode()+b'"\r\n\r\n'+value.encode()+b'\r\n'
    return base64.b64encode(body+b'--b--\r\n').decode()
def run(output):
    base=dict(Body=multipart(),ContentType='multipart/form-data; boundary=b',User=U,Workspace=W,Query='',Failure='',Storage=True,Cancelled=False,Stable=False)
    fixtures=[dict(base,Body=multipart(fields),Failure=failure,Cancelled=cancelled) for fields in [[],[('issue_id',I)],[('comment_id',C)],[('issue_id',I),('comment_id',C)]] for failure in ['', 'member','upload','upload-cancel','begin','execute','create','create-cancel','commit','lock-missing','lock-cancel'] for cancelled in [False,True]]
    fixtures.extend(dict(base,Workspace=workspace,User=user,Storage=storage,Body=multipart(fields)) for workspace in ['',W] for user in ['',U] for storage in [False,True] for fields in [[('issue_id','invalid')],[('comment_id','invalid')],[('task_id',I)]])
    fixtures.extend(dict(base,Body=multipart(filename=name,data=data),Query=query,Stable=stable) for name,data in [('报告.json',b'{}'),('empty',b''),('file.txt',b'hello')] for query in ['', 'issue_id='+I,'issue_id=invalid','x=a;b'] for stable in [False,True])
    fixtures.extend(dict(base,Body=multipart(fields),Revisions=True,Failure=failure,Stable=stable) for fields in [[('issue_id',I)],[('comment_id',C)],[('issue_id',I),('comment_id',C)]] for failure in ['', 'comment_event','reactions','attachments'] for stable in [False,True])
    agent='eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee';task='ffffffff-ffff-ffff-ffff-ffffffffffff';session='11111111-1111-1111-1111-111111111111'
    fixtures.extend(dict(base,Source='task_token',Agent=actor,Task=bound,TaskAgent=stored,TaskSession=chat,Body=multipart([('task_id',form)]),Failure=failure) for actor,bound,stored,chat,form in [(agent,task,agent,session,task),(agent,task.upper(),agent,session,task),(agent.upper(),task,agent,session,task),(agent,task,agent,'',task),(agent,task,I,session,task),(agent,task,agent,session,I),(agent,task,agent,session,'invalid'),(agent,task,agent,session,task.replace('-',''))] for failure in ['', 'source_task','upload_task','upload_task-cancel'])
    fixtures.extend(dict(base,Source=source,Agent=agent if source else '',Task=task if with_task else '',TaskAgent=agent,TaskSession=I,Session=session,Creator=creator,Body=multipart([('chat_session_id',form)]+([('task_id',task)] if with_task else [])),Failure=failure) for source,with_task in [('',False),('task_token',False),('task_token',True)] for creator,form in [(U,session),(I,session),(U,'invalid')] for failure in ['', 'session','agent','public_session'])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_uploads"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_uploads.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-uploads-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/attachment-uploads-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[asyncio.run(evaluate(f,result['generated_id'])) for f,result in zip(fixtures,go)]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/go/internal/handler/wakeup_actor.go','server/tests/parity/go_attachment_uploads/main.go','server/tests/parity/go_attachment_uploads/wrapper.go','server/src/workpal_backend/files/uploads.py','server/src/workpal_backend/files/mutations.py','server/src/workpal_backend/auth/wakeup_actor.py','server/src/workpal_backend/auth/actor.py','server/src/workpal_backend/files/upload_bindings.py','server/src/workpal_backend/files/upload_task_binding.py','server/src/workpal_backend/files/write_transactions.py','server/src/workpal_backend/files/metadata.py','server/src/workpal_backend/files/upload_form.py','server/src/workpal_backend/files/events.py','server/src/workpal_backend/comments/groups.py','server/src/workpal_backend/comments/projection.py','server/src/workpal_backend/infrastructure/go_time.py','server/tools/run_attachment_uploads_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Actual UploadFile multipart through strict original generated DB rows and transaction/storage fixtures: status/JSON payload/query order/transaction attribution/cleanup/byte hash and synchronous original event bus payloads after positive revisions. Python invokes request-scoped AttachmentMutations and injects the observed random Go UUID; UUID generator separately certified. No actual SQL row-lock/concurrency, authentication middleware or live upload activation certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
