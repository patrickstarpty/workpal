"""Invoke the actual unexported Go merge helper through a disposable wrapper."""
from pathlib import Path
import hashlib
import json
import sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.agents.env_update import merge_env,decode_update


def run(output):
    cases=[dict(Existing=a,Requested=b) for a,b in [
        ({},{}),({'a':'secret'},{}),({}, {'a':'****'}),({'a':'secret'},{'a':'****'}),
        ({'a':'secret'},{'a':'new'}),({'a':'same'},{'a':'same'}),({}, {'a':''}),
        ({'keep':'secret','same':'same','change':'old','remove':'gone'},
         {'keep':'****','new-mask':'****','same':'same','change':'new','z':'last','a':''}),
        ({'a':'****'},{'a':'****'}),({'z':'old','中':'old','a':'old'},{'中':'new','a':'new','z':'new'}),
    ]]
    cases += [dict(Body=body) for body in [
        'null','{}','{"custom_env":null}','{"custom_env":{"x":null}}',
        '{"custom_env":{"a":"first"},"CUSTOM_ENV":{"b":"next"}}',
        '{"custom_env":{"a":"first"},"custom_env":null}',
        '{"custom_env":{"x":"value","x":null}}',
        '{"custom_env":{"x":"value"}} trailing','','[]','{"custom_env":[]}',
        '{"custom_env":{"a":1}}','{"custom_env":{"a":1},"custom_env":{}}',
        '{"custom_env":{"a":false}}',
    ]]
    cases.append(dict(Body='{"ignored":'+'9'*5000+',"custom_env":{"a":"ok"}}'))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_env_merge"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/export.go /work/internal/handler/parity_env_export.go && cd /work && go build -mod=readonly -p=4 -o /out/env-merge-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/env-merge-oracle'],input=json.dumps(cases))
    go=json.loads(result.stdout)
    python=[]
    for case in cases:
        if 'Body' in case:
            try:python.append(dict(decoded=decode_update(case['Body'].encode())))
            except ValueError:python.append(dict(error='invalid request body'))
        else:
            merged,audit=merge_env(case['Existing'],case['Requested'])
            python.append(dict(merged=merged,audit=audit))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/agent_env.go','server/tests/parity/go_env_merge/export.go',
             'server/tests/parity/go_env_merge/main.go','server/src/workpal_backend/agents/env_update.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go mergeAgentEnv helper and UpdateAgentEnvRequest decoder only; not full PUT HTTP transaction/events.',
        fixtures=cases,go=go,python=python,mismatches=mismatches,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        binary_sha256=hashlib.sha256((binaries/'env-merge-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),mismatches=mismatches)))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
