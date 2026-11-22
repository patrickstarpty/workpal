"""Original signed attachment metadata dispatch, presigning failures and capabilities."""
from pathlib import Path
import hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
import asyncio
from urllib.parse import urlsplit,parse_qs
from workpal_backend.files.metadata import AttachmentMetadata
from workpal_backend.files.capabilities import AttachmentCapabilities
from workpal_backend.infrastructure.go_response import GoJSONResponse
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
SECRET='public-parity-metadata-fixture-not-a-production-secret'
class Storage:
    is_local=False
    def __init__(self,f,calls):self.f,self.calls=f,calls
    def cdn_domain(self):return ''
    def key_from_url(self,url):self.calls.append(['key',url]);return 'key'
class Presigner(Storage):
    def presign_get_with_content_disposition(self,key,ttl,disposition):
        self.calls.append(['presign',key,ttl,disposition]);kind='download' if disposition else 'inline'
        if self.f['Failure']==kind:raise RuntimeError('sign failed')
        if self.f['Failure']==kind+'-cancel':raise asyncio.CancelledError()
        if self.f['Failure']==kind+'-empty':return ''
        return 'https://cdn.example/'+kind
async def evaluate(f,observed):
    calls=[];storage=None if f['Store']=='none' else (Presigner if f['Store']=='presigner' else Storage)(f,calls)
    # Original Go samples time.Now independently for the two capabilities.
    # Replay only those observed expiry instants; compare complete signatures.
    times=[]
    for field in ['download_url','attachment_download_url']:
        url=observed['body'].get(field,'');expiry=parse_qs(urlsplit(url).query).get('exp')
        if expiry:times.append((int(expiry[0])-60)*10**9)
    clock=iter(times)
    metadata=AttachmentMetadata(storage,ttl_nanoseconds=f['TTL'],mode=f['Mode'],capabilities=AttachmentCapabilities(SECRET),clock_ns=lambda:next(clock))
    attachment=dict(id=A,workspace_id=W,uploader_type='member',uploader_id=None,filename=f['Filename'],url=f['URL'],content_type=f['ContentType'],size_bytes=3,created_at=None)
    body=await metadata.signed_response(attachment)
    return dict(status=200,body=body,raw_body=GoJSONResponse(body).body.decode(),calls=calls)
def run(output):
    base=dict(Mode='auto',Store='none',Failure='',URL='https://cdn.example/file',Filename='报告.pdf',ContentType='application/pdf',TTL=0,Stable=False)
    fixtures=[dict(base,Mode=mode,Store=store,Stable=stable,URL=url) for mode in ['auto','proxy','presign','cloudfront','invalid'] for store in ['none','plain','presigner'] for stable in [False,True] for url in ['https://cdn.example/file','http://localhost/file','/uploads/file']]
    fixtures.extend(dict(base,Store='presigner',Failure=failure,TTL=ttl,Filename=name,ContentType=media) for failure in ['', 'inline','download','inline-cancel','download-cancel','inline-empty','download-empty'] for ttl in [-1,1,120000000000] for name,media in [('image.png','image/png'),('report.txt','text/plain')])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1';binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro','-v',f'{ROOT/"server/tests/parity/go_signed_metadata"}:/harness:ro','-v',f'{binaries}:/out','-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build','-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=','-e','GOMAXPROCS=4','golang:1.26.9','sh','-c','mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_signed_metadata.go && cd /work && go build -mod=readonly -p=4 -o /out/signed-metadata-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-e','JWT_SECRET='+SECRET,'-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/signed-metadata-oracle'],input=json.dumps(fixtures[offset:offset+32]));go.extend(json.loads(result.stdout))
    python=[asyncio.run(evaluate(f,g)) for f,g in zip(fixtures,go)];assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/go/internal/handler/attachment_capability.go','server/tests/parity/go_signed_metadata/main.go','server/tests/parity/go_signed_metadata/wrapper.go','server/tools/run_signed_metadata_parity.py','server/src/workpal_backend/files/metadata.py','server/src/workpal_backend/files/attachment_urls.py','server/src/workpal_backend/files/capabilities.py','server/src/workpal_backend/infrastructure/go_time.py']
    Path(output).write_text(json.dumps(dict(scope='Original writeSignedAttachmentMetadata exact JSON response bytes and mode dispatch, independent presign results, empty URLs, stable capability ignored, and signed proxy capabilities. Python clock replays observed Go expiry instants; complete signatures compared with public fixture JWT key. Successful CloudFront signing separately certified, no HTTP permission middleware or live storage calls.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)));return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:print(error.stderr,file=sys.stderr);raise
