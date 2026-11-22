"""Invoke the actual unexported Go merge helper through a disposable wrapper."""
from pathlib import Path
import hashlib
import json
import sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.avatar_urls import AvatarURLs,LocalObjectURLs,content_type,redirect_max_age


def run(output):
    secret='fixture-avatar-secret-only'
    policy=AvatarURLs(secret)
    cases=[]
    for key in ['users/user/avatar.PNG','users/user/.png','avatar.svg','space name.png','unicode-头像.webp','a.png/']:
        for base in ['', 'https://files.example/']:
            storage=LocalObjectURLs(base)
            cases.append(dict(Raw=storage.object_url(key),Key=key,Base=base,Public='https://api.example///',Disabled=False,TTL=119.9))
    key='users/user/avatar.png'
    served=policy.path(key)
    for raw in [served,'https://api.example'+served,'https://unrelated.example'+served,
                served+'?x=1','https://api.example'+served+'?x=1',served.replace('avatar.png','changed.png'),
                'https://external.example/uploads/avatar.png','data:image/png;base64,AAAA','emoji:smile','']:
        cases.append(dict(Raw=raw,Key=key,Base='',Public='',Disabled=False,TTL=0.5))
    cases.append(dict(Raw='/uploads/avatar.png',Key='avatar.png',Base='',Public='',Disabled=True,TTL=300))
    cases.extend(dict(Raw='',Key='avatar.png',Base='',Public='',Disabled=False,TTL=ttl) for ttl in [0,-1,1.9,2,120])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_avatar_urls"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/export.go /work/internal/handler/parity_avatar_export.go && cd /work && go build -mod=readonly -p=4 -o /out/avatar-urls-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-e',f'JWT_SECRET={secret}','-e','LOCAL_UPLOAD_DIR=/tmp/avatar-fixture','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/avatar-urls-oracle'],input=json.dumps(cases))
    go=json.loads(result.stdout)
    python=[]
    for case in cases:
        policy=AvatarURLs(secret,None if case['Disabled'] else LocalObjectURLs(case['Base']),case['Public'])
        served=policy.key_from_served(case['Raw'])
        python.append(dict(signature=policy.sign(case['Key']),path=policy.path(case['Key']),content_type=content_type(case['Key']),
            resolved=policy.resolve(case['Raw']),normalized=policy.normalize(case['Raw']),served_key=served or '',
            valid=served is not None,max_age=redirect_max_age(case['TTL'])))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/avatar.go','server/go/internal/storage/local.go',
             'server/tests/parity/go_avatar_urls/export.go','server/tests/parity/go_avatar_urls/main.go',
             'server/src/workpal_backend/files/avatar_urls.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go avatar signature/URL projection helpers with local storage; no attachment lookup, storage read, proxy/presign/CloudFront, or HTTP transport certification.',
        fixtures=cases,go=go,python=python,mismatches=mismatches,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        binary_sha256=hashlib.sha256((binaries/'avatar-urls-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),mismatches=mismatches)))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
