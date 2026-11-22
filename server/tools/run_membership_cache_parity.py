"""Original Go membership cache command semantics against Python."""
from pathlib import Path
import hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.auth.membership_cache import MembershipCache
class Client:
    def __init__(self,f):self.f=f;self.calls=[]
    def check(self):
        if self.f['Failure']:raise RuntimeError(self.f['Failure'])
    def get(self,key):
        self.calls.append(['get',key]);self.check()
        return self.f['Value'] if self.f['Present'] else None
    def set(self,key,value,*,ex):
        self.calls.append(['set',key,value,ex]);self.check()
    def delete(self,key):
        self.calls.append(['delete',key]);self.check()

def run(output):
    fixtures=[dict(Disabled=disabled,User=user,Workspace=workspace,Value=value,Present=present,Failure=failure)
        for disabled in [False,True] for user,workspace in [('user','workspace'),('',''),('u:x','w:y'),('用户','工作区')]
        for value in ['', '0', '1', 'arbitrary'] for present in [False,True] for failure in ['', 'unavailable']]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_membership_cache"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/membership-cache-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/membership-cache-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for f in fixtures:
        client=Client(f);cache=MembershipCache(None if f['Disabled'] else client)
        hit=cache.get(f['User'],f['Workspace'])
        cache.set(f['User'],f['Workspace']);cache.invalidate(f['User'],f['Workspace'])
        python.append(dict(hit=hit,calls=client.calls))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/auth/membership_cache.go','server/tests/parity/go_membership_cache/main.go','server/src/workpal_backend/auth/membership_cache.py','server/tools/run_membership_cache_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go membership cache: disabled cache, raw key composition, presence not value truthiness, command order, TTL, and client error fallback. Injected command outcomes; real Redis lifecycle tested separately; no transport retry/cancellation timing certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
