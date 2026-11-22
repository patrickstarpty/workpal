"""Invoke original Go Client.handleFrame using a disposable package wrapper."""
from pathlib import Path
import ast,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.protocol import parse_frame
from workpal_backend.infrastructure.go_response import marshal_map_json

def run(output):
    tree=ast.parse((ROOT/'server/tests/test_realtime_frame_decode.py').read_text())
    test=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='test_go_frame_decoding')
    raw_cases=[raw for raw,_ in ast.literal_eval(test.decorator_list[0].args[1])]
    raw_cases += ['null','[]','{}','true','{"type":"unknown"}',
        '{"type":"subscribe"}','{"type":"subscribe","payload":[]}',
        '{"type":"subscribe","payload":{"scope":"workspace","id":"foreign"}}',
        '{"type":"subscribe","payload":{"scope":"user","id":"u"}}',
        '{"type":"subscribe","payload":{"scope":"chat","id":"c"}}',
        '{"type":"subscribe","payload":{"scope":"task","id":"t"}}',
        '{"type":"subscribe","payload":{"scope":"workspace_member","id":"w:u"}}',
        '{"type":"unsubscribe","payload":{"scope":"arbitrary","id":"x"}}',
        '{"type":"subscribe","payload":{"scope":7,"scope":"chat","id":"x"}}',
        '{"type":"ping","unknown":'+('9'*5000)+'}',
        '{"type":"subscribe","payload":{"scope":"chat","id":"x","unknown":1e999}}']
    for depth in [100,900,1100,2000,9999,10000]:
        raw_cases.append('{"type":"ping","unknown":'+'['*depth+'0'+']'*depth+'}')
    raw_cases.append('{"type":"subscribe","payload":{"scope":"workspace","id":"w","unknown":'+'{"x":'*1100+'null'+'}'*1100+'}}')
    for leaf in ['[1,]','{"x":}','{"x":1,}','01','1.','1e+','NaN','"bad\\x"','[true false]']:
        raw_cases.append('{"type":"ping","unknown":'+'['*1100+leaf+']'*1100+'}')
    seed='{'+ '"type":"subscribe","payload":{"scope":"workspace","id":"w","unknown":[true,false,null,1e-7,{"x":"a"}]}}'
    raw_cases.extend(seed[:index]+seed[index+1:] for index in range(len(seed)))
    fixtures=[dict(Raw=base64.b64encode(raw if isinstance(raw,bytes) else raw.encode()).decode(),Mode=mode) for raw in raw_cases for mode in ['deny','allow','error']]
    for value in [dict(type='fixture',payload={'z':'<>&\u2028\u2029','a':1e-7,'negative':-0.0}),
                  {'array':[None,True,False,1e21,1e-6],'unicode':'中文😀'},
                  {'z':{'nested':{'b':2,'a':1}},'a':[]}]:
        fixtures.append(dict(Raw=base64.b64encode(json.dumps(value,ensure_ascii=False).encode()).decode(),Mode='marshal'))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_ws_frames"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_export.go && cd /work && go build -mod=readonly -p=4 -o /out/ws-frames-oracle ./parity'])
    # Each fixture starts a fresh Hub; separate bounded processes preserve that
    # isolation while avoiding long-lived emulated-runtime instability.
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
            '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
            '/out/ws-frames-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for fixture in fixtures:
        calls=[]
        def auth(*args):
            calls.append(list(args))
            if fixture['Mode']=='error':raise RuntimeError('fixture query outage')
            return fixture['Mode']=='allow'
        raw=base64.b64decode(fixture['Raw'])
        reply=json.loads(raw,parse_int=float) if fixture['Mode']=='marshal' else parse_frame(raw,'w','u',authorizer=auth).reply
        python.append(dict(reply=reply,raw=marshal_map_json(reply).decode() if reply is not None else None,calls=calls))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/hub.go','server/tests/parity/go_ws_frames/wrapper.go','server/tests/parity/go_ws_frames/main.go','server/src/workpal_backend/realtime/frame_decode.py','server/src/workpal_backend/realtime/protocol.py','server/src/workpal_backend/infrastructure/go_response.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go Client.handleFrame reply objects, exact send-channel JSON bytes and authorizer call arguments/order with isolated allow/deny/error authorizer. Includes direct sendJSON map/float/HTML fixtures. No socket transport, read-limit enforcement, nil-authorizer mode, room callbacks/metrics, or exhaustive JSON grammar equivalence certified. Includes observed depth-limit and deterministic syntax-deletion fixtures.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'ws-frames-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
