"""Execute original Go private-project event reference extraction."""
from pathlib import Path
import hashlib
import json
import sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.event_refs import extract_event_refs

def run(output):
    fixtures=[]
    def add(kind,payload):fixtures.append(dict(type=kind,payload=payload))
    for kind in ['project:updated','project_resource:created','project_folder:filed','project_folder:other','issue:deleted','unknown']:
        for payload in [{'project':{'id':'nested'},'project_id':'top'},{'project_id':'top'},{'project_id':None},{'project_id':7}]:add(kind,payload)
    for kind in ['issue:updated','autopilot:updated','comment:updated']:
        for value in [None,'',7,'p',False,[],{}]:
            add(kind,{'issue':{'project_id':value,'id':'i'},'autopilot':{'project_id':value},'autopilot_id':'a','comment':{'id':'c','issue_id':'ci'}})
    for payload in [
        {'issue':{'id':None},'issue_id':'fallback','comment_id':'c'},
        {'comment':{'id':'c','issue_id':None},'comment_id':'fallback'},
        {'linked_issue_ids':['i',None,23,'j',{},True]},
        {'linked_issue_ids':[]},{'linked_issue_ids':None},{'linked_issue_ids':'invalid'},
        {'issue_id':'i','linked_issue_ids':['other']},{'comment_id':'c','linked_issue_ids':['other']},
        None,[],42,'text',{'issue':[]}]:add('pull_request:updated',payload)
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_event_refs"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /work/cmd/server/private_project_realtime.go /work/parity/private_project_realtime.go && cd /work && go build -mod=readonly -p=4 -o /out/event-refs-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/event-refs-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[vars(extract_event_refs(f['type'],f['payload'])) for f in fixtures]
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/cmd/server/private_project_realtime.go','server/go/ee/projectfolder/handler.go','server/tests/parity/go_event_refs/main.go','server/src/workpal_backend/realtime/event_refs.py']
    Path(output).write_text(json.dumps(dict(scope='Original extractEventRefs with actual EE projectfolder initialization. JSON payload reference precedence/null/malformed element handling; no audience SQL/cache/transport coverage.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'event-refs-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
