"""Original WS handler denials versus Python ASGI route and request values."""
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
import asyncio,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from fastapi import FastAPI
from workpal_backend.realtime.routes import router
from workpal_backend.realtime.origins import OriginPolicy
from workpal_backend.realtime.request_values import query_value,first_cookie

async def observe(f):
    app=FastAPI();app.include_router(router);slugs=[];messages=[]
    class Database:
        @contextmanager
        def transaction(self):yield self
        def execute(self,statement):
            slug=statement.compile().params['slug_1'];slugs.append(slug)
            return SimpleNamespace(scalar=lambda:'workspace' if slug=='good' else None)
    app.state.database=Database();app.state.settings=SimpleNamespace(auth_secret='s'*32)
    app.state.ws_origin_policy=OriginPolicy([])
    headers=[(b'host',b'internal'),(b'origin',b'https://forbidden.example')]
    headers.extend((b'cookie',line.encode()) for line in f['Cookies'])
    scope=dict(type='websocket',asgi={'version':'3.0'},scheme='ws',path='/ws',raw_path=b'/ws',root_path='',
               query_string=f['Query'].encode(),headers=headers,client=('192.0.2.1',1234),server=('internal',80),
               subprotocols=[],extensions={'websocket.http.response':{}})
    received=False
    async def receive():
        nonlocal received
        if received:raise RuntimeError('Unexpected acceptance of denial fixture')
        received=True;return {'type':'websocket.connect'}
    async def send(message):messages.append(message)
    await app(scope,receive,send)
    starts=[m for m in messages if m['type']=='websocket.http.response.start']
    assert len(starts)==1,messages
    response=starts[0];body=b''.join(m.get('body',b'') for m in messages if m['type']=='websocket.http.response.body')
    h={key.decode().lower():value.decode() for key,value in response['headers']}
    cookie=first_cookie(f['Cookies'],'workpal_auth')
    return dict(workspace=base64.b64encode(query_value(f['Query'].encode(),'workspace_id').encode('utf8','surrogateescape')).decode(),
                cookie=cookie or '',has_cookie=cookie is not None,slugs=slugs,status=response['status'],
                headers={key:h.get(key.lower(),'') for key in ['Content-Type','X-Content-Type-Options','Sec-WebSocket-Version']},body=base64.b64encode(body).decode())

def run(output):
    queries=['','workspace_id=w','workspace_id=&workspace_id=w','workspace_id=w&workspace_id=',
             'workspace_id=bad%zz&workspace_id=w','workspace_id=bad;ignored&workspace_id=w',
             'workspace_id=bad;ignored','workspace%5fid=w','workspace_id=a+b','workspace_id=%ff',
             'workspace_slug=good','workspace_slug=bad','workspace_slug=bad&workspace_slug=good',
             'workspace_id=&workspace_slug=good','workspace_id=w&workspace_slug=bad']
    cookies=[[],['workpal_auth=bad'],['workpal_auth=; workpal_auth=bad'],['workpal_auth=bad; workpal_auth='],
             ['workpal_auth="bad"'],['workpal_auth=bad\\value; workpal_auth='],
             ['workpal_auth=','workpal_auth=bad'],['other=x','workpal_auth=bad'],
             ['workpal_auth= value '],['workpal_auth=\u00ff'],['workpal_auth="bad'],['workpal_auth']]
    fixtures=[dict(Query=query,Cookies=cookie) for query in queries for cookie in cookies]
    fixtures.extend(dict(Query='workspace_id=w',Cookies=['workpal_auth=bad;'+'x=1;'*count]) for count in [2998,2999,3000])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_ws_request"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_ws_request.go && cd /work && go build -mod=readonly -p=4 -o /out/ws-request-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/ws-request-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/hub.go','server/tests/parity/go_ws_request/main.go',
             'server/tests/parity/go_ws_request/wrapper.go','server/src/workpal_backend/realtime/request_values.py',
             'server/src/workpal_backend/realtime/routes.py','server/src/workpal_backend/realtime/origins.py',
             'server/src/workpal_backend/auth/errors.py','server/tools/run_ws_request_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original HandleWebSocket HTTP denials vs actual Python ASGI route: duplicate/malformed query values, Cookie selection/3000-cookie limit, slug resolver order, invalid-cookie-before-origin precedence, exact status/body and semantic denial headers. Slug storage dependency fixture; no successful upgrade, valid-token membership, HTTP framing or middleware-stack certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
