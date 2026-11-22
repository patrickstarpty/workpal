"""Original attachment URL policy versus Python without network access."""
from pathlib import Path
from types import SimpleNamespace
import hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.attachment_urls import AttachmentURLs,durable_public_url,normalize_download_mode,stable_urls_requested,download_ttl,should_proxy_url,resolve_download_mode

def run(output):
    urls=['','/uploads/a','https:///a','https://cdn.test/a','HTTPS://cdn.test/a','ftp://cdn.test/a','https://cdn.test/a?Signature=x','https://cdn.test/a?Signature=&Signature=x','https://cdn.test/a?signature=x','https://cdn.test/a?Signature=%zz','https://cdn.test/a?Signature=x;ignored','https://cdn.test/%zz','https://u:p@cdn.test/a','https://[::1]/a','https://bad host/a','https://cdn.test:abc/a','https://cdn.test/a#%zz']
    urls += ['https://cdn.test/a?'+key+'='+value for key in ['Signature','X-Amz-Signature','Key-Pair-Id','Expires','X-Amz-Expires'] for value in ['', '1','%ff','%20']]
    fixtures=[dict(URL=url,Store=store,CDN=cdn,Signed=signed,PublicURL=public,Mode='auto',Capability='',TTL=0) for url in urls for store,cdn,signed in [('none','',False),('local','',False),('remote','',False),('remote','cdn.test',False),('remote','cdn.test',True)] for public in ['', 'https://app.test///']]
    fixtures.extend(dict(URL='https://cdn.test/a',Store='remote',CDN='cdn.test',Signed=False,PublicURL='',Mode=mode,Capability=cap,TTL=ttl) for mode in ['', 'AUTO', 'presign',' proxy ','cloudfront','invalid','\u0085PRESIGN\u00a0'] for cap in ['', 'other, stable_attachment_urls', 'STABLE_ATTACHMENT_URLS','\u0085stable_attachment_urls\u00a0'] for ttl in [-1,0,1,1800000000000])
    hosts=['localhost','LOCALHOST.','sub.localhost','minio','foo.local','foo.localdomain','foo.internal','foo.lan','foo.home','foo.docker','public.example.','0.0.0.0','127.0.0.1','10.1.2.3','172.15.0.1','172.16.0.1','172.31.255.255','172.32.0.1','192.168.1.1','169.254.0.1','224.0.0.1','224.0.1.1','192.0.2.1','198.18.0.1','203.0.113.1','100.64.0.1','8.8.8.8','[::]','[::1]','[2001:4860:4860::8888]','[::ffff:0.0.0.0]','[::ffff:127.0.0.1]','[::ffff:10.1.2.3]','[::ffff:224.0.0.1]','[::ffff:8.8.8.8]','[::%25foo.bar]','[::1%25foo.bar]','[fe80::1%25foo.bar]']
    fixtures.extend(dict(URL='https://'+host+'/a',Store='remote',CDN='cdn.test',Signed=signed,Presigner=presigner,PublicURL='',Mode=mode,Capability='',TTL=0) for host in hosts for mode in ['auto','cloudfront','presign','proxy'] for signed,presigner in [(False,False),(False,True),(True,True)])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_urls"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_urls.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-urls-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/attachment-urls-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for f in fixtures:
        storage=None if f['Store']=='none' else SimpleNamespace(is_local=f['Store']=='local',cdn_domain=lambda:f['CDN'])
        policy=AttachmentURLs(storage,object() if f['Signed'] else None,public_url=f['PublicURL'])
        mode,valid=normalize_download_mode(f['Mode'])
        python.append(dict(proxy=should_proxy_url(f['URL']),resolved=resolve_download_mode(f['Mode'],f['URL'],signer=f['Signed'],presigner=f.get('Presigner',False)),durable=durable_public_url(f['URL']),public=policy.publicly_readable(f['URL']),markdown=policy.markdown_url('attachment',f['URL']),mode=mode,valid_mode=valid,ttl=download_ttl(f['TTL']),stable=stable_urls_requested(f['Capability'])))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/go/internal/handler/daemon.go','server/tests/parity/go_attachment_urls/main.go','server/tests/parity/go_attachment_urls/wrapper.go','server/src/workpal_backend/files/attachment_urls.py','server/src/workpal_backend/realtime/origins.py','server/src/workpal_backend/realtime/request_values.py','server/src/workpal_backend/auth/profile_decode.py','server/src/workpal_backend/workspaces/decode.py','server/tools/run_attachment_urls_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original URL durability/public storage/Markdown fallback/download mode/TTL/client capability helpers vs Python. Isolated storage and signer presence, no object fetch/signing or full attachment response certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
