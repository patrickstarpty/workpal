"""Original attachment download capability signatures versus Python."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.capabilities import AttachmentCapabilities

SIGNER=AttachmentCapabilities('fixture-attachment-capability-secret-only-32bytes')
def observe(f):
    signature=SIGNER.sign(f['SignID'],f['Expiry'],f['SignIntent']);mode=f['SignatureMode']
    sig={'upper':signature.upper(),'space':signature[:2]+' '+signature[2:],'short':signature[:62],'odd':signature[:63],'bad':'xx','empty':''}.get(mode,signature)
    return dict(signature=signature,path=SIGNER.path(f['ID'],now_ns=f['Now']),download_path=SIGNER.path(f['ID'],now_ns=f['Now'],download=True),valid=SIGNER.verify(f['ID'],f['RawExpiry'],sig,intent=f['Intent'],now_ns=f['Now']))

def run(output):
    fixtures=[]
    for identity in ['attachment','11111111-1111-4111-8111-111111111111','','附件']:
        for raw in ['60','+60','00060',' 60','60 ','６０','59','61','','9223372036854775808','0'*5000+'60']:
            for intent in ['', 'attachment']:
                fixtures.append(dict(ID=identity,SignID=identity,Expiry=60,RawExpiry=raw,SignIntent=intent,Intent=intent,Now=0,SignatureMode=''))
        for mode in ['', 'upper','space','short','odd','bad','empty']:
            for now in [-1,60_999_999_999,61_000_000_000]:
                fixtures.append(dict(ID=identity,SignID=identity,Expiry=60,RawExpiry='60',SignIntent='',Intent='',Now=now,SignatureMode=mode))
        for sign_id,intent in [('other',''),(identity,'attachment')]:
            fixtures.append(dict(ID=identity,SignID=sign_id,Expiry=60,RawExpiry='60',SignIntent='',Intent=intent,Now=0,SignatureMode=''))
    for expiry in [-9223372036854775808,-1,0,9223372036854775807]:
        fixtures.append(dict(ID='attachment',SignID='attachment',Expiry=expiry,RawExpiry=str(expiry),SignIntent='',Intent='',Now=-1,SignatureMode=''))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_capabilities"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_capabilities.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-capabilities-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-e','JWT_SECRET=fixture-attachment-capability-secret-only-32bytes','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/attachment-capabilities-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[observe(f) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/attachment_capability.go','server/tests/parity/go_attachment_capabilities/main.go','server/tests/parity/go_attachment_capabilities/wrapper.go','server/src/workpal_backend/files/capabilities.py','server/src/workpal_backend/files/ranges.py','server/tools/run_attachment_capabilities_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original attachment capability signing/path/verification vs Python: HMAC domain, load/download intent, expiry second boundary, decimal int64 and hex rules. Fixed non-production fixture JWT secret; no minting authorization, public redemption route, storage access or key rotation lifecycle certified.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
