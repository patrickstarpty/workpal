"""Compare original server environment helpers and pinned Go duration parsing."""
from pathlib import Path
from dataclasses import asdict
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.relay_config import relay_config_from_env,parse_duration
from workpal_backend.realtime.origins import router_origins

def run(output):
    environments=[{}]
    for key,values in {
        'MODE':['','legacy','dual','SHARDED',' \u2003DUAL ','unknown','\u001clegacy'],
        'SHARDS':['0','-1','+3',' 3','3 ','01','1_000',str((1<<63)-1),str(1<<63)],
        'STREAM_MAXLEN':['0','-1','+3',' 3',str(1<<63)],
        'XREAD_COUNT':['0','-1','+3',' 3',str(1<<63)],
        'STREAM_TTL_ENABLED':['true','TRUE','True','t','1','false','0','yes',' true','TrUe'],
        'REPLAY_GRACE':['1.5s','1ns','0','-1s','9223372036854775807ns','+3m'],
        'TRIM_HORIZON':['1ns','0','-1s','1h'],
        'STREAM_TTL':['1ns','0','-1s','1h'],
        'TTL_REFRESH_INTERVAL':['1ns','0','-1s','1h'],
        'MAINTENANCE_INTERVAL':['1ns','0','-1s','1h'],
    }.items():
        environments.extend({'REALTIME_RELAY_'+key:value} for value in values)
    durations=['0','+0','-0','','1',' 1s','1s ','1e3s','.s','1.s','.5s','+.5us','1µs1μs','1h2m3.000000004s','１s',
               '9223372036854775807ns','9223372036854775808ns','-9223372036854775808ns','-9223372036854775809ns',
               '2562047h47m16.854775807s','2562047h47m16.854775808s','0.33333333333333333333333333333h',
               '.9999999999999999999999999999ns','000000000000000000000000000001s']
    fixtures=[dict(Env=env,Cluster=cluster,Duration='1s') for env in environments for cluster in [False,True]]
    fixtures.extend(dict(Env={'REALTIME_RELAY_XREAD_BLOCK':d},Cluster=False,Duration=d) for d in durations)
    fixtures.extend(dict(Env=env,Cluster=False,Duration='1s') for env in [
        {'ALLOWED_ORIGINS':'https://ignored'}, {'CORS_ALLOWED_ORIGINS':', ,'},
        {'FRONTEND_ORIGIN':' https://front , https://second '},
        {'CORS_ALLOWED_ORIGINS':'https://cors','FRONTEND_ORIGIN':'https://front'},
        {'CORS_ALLOWED_ORIGINS':' \u2003 ','FRONTEND_ORIGIN':'https://front'},
        {'CORS_ALLOWED_ORIGINS':',','FRONTEND_ORIGIN':'https://front'}])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_relay_config"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work && cp -a /reference/server/go/. /work/ && cp /harness/wrapper.go /work/cmd/server/parity_relay_config.go && cd /work && go build -mod=readonly -p=4 -o /out/relay-config-oracle ./cmd/server'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/relay-config-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    for f in fixtures:
        mode,c=relay_config_from_env(f['Env'])
        error=''
        try:relay_config_from_env(f['Env'],cluster_mode=f['Cluster'])
        except ValueError as caught:error=str(caught)
        duration=0;valid=True
        try:duration=parse_duration(f['Duration'])
        except ValueError:valid=False
        python.append(dict(origins=router_origins(f['Env']),mode=mode,error=error,config=list(asdict(c).values()),duration=duration,valid_duration=valid))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/cmd/server/router.go','server/src/workpal_backend/realtime/origins.py','server/go/cmd/server/main.go','server/go/internal/realtime/sharded_stream_relay.go',
             'server/tests/parity/go_relay_config/wrapper.go','server/src/workpal_backend/realtime/relay_config.py',
             'server/src/workpal_backend/realtime/sharded_config.py']
    Path(output).write_text(json.dumps(dict(scope='Original server allowedOrigins and env mode/config helpers and cluster validation, Go1.26.9 ParseDuration values and validity. Logs and ParseDuration error wording excluded; no boot/client-configuration certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
