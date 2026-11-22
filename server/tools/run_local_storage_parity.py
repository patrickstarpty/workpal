"""Invoke the actual unexported Go merge helper through a disposable wrapper."""
from pathlib import Path
import hashlib
import json
import sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
import io
import tempfile
from workpal_backend.files.local_storage import LocalStorage


def run(output):
    cases=[dict(Op=op,Key=key,Data=data,Type='image/png',Filename=filename,Broken=broken) for op,key,data,filename,broken in [
        ('upload','users/u/a.png','original','display<&>.png',False),
        ('read','users/u/a.png','','',False),('upload','users/u/a.png','','new.png',True),
        ('read','users/u/a.png.meta.json','','',False),('read','users/u/.a.png.tmp','','',False),
        ('upload','users/u/a.png','replacement','',False),
        ('fixture-file','users/u/.a.png.tmp','crash','',False),
        ('delete','users/u/a.png','','',False),('delete','users/u/a.png','','',False),
        ('fixture-dir','.blocked.tmp','','',False),('upload','blocked','body','',False),
        ('fixture-dir','sidecar.png.meta.json','','',False),('upload','sidecar.png','body','name.png',False),
        ('delete','sidecar.png','','',False),
        ('from-reader','new/failed.png','','new.png',True),
        ('from-reader','new/good.png','good','good.png',False),
        ('read','../outside','','',False),('read','','','',False),
        ('upload','/leading.png','body','',False),('read','/leading.png','','',False),
        ('upload','notes.tmp','body','',False),('read','notes.tmp','','',False),
    ]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_local_storage"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/local-storage-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/local-storage-oracle'],input=json.dumps(cases))
    go=json.loads(result.stdout)
    python=[]
    class Broken:
        def __init__(self):self.sent=False
        def read(self,size=-1):
            if self.sent:raise OSError('fixture read failure')
            self.sent=True;return b'partial'
    with tempfile.TemporaryDirectory(prefix='workpal-local-storage-') as tmp:
        root=Path(tmp);store=LocalStorage(root,'https://files.example/')
        for case in cases:
            value='';ok=True
            try:
                op,key=case['Op'],case['Key']
                if op in ('upload','from-reader'):
                    reader=Broken() if case['Broken'] else io.BytesIO(case['Data'].encode())
                    if op=='upload':value=store.upload_stream(key,reader,999,case['Type'],case['Filename'])
                    else:value=store.upload_from_reader(key,reader,case['Type'],case['Filename'])
                elif op=='read':
                    with store.get_reader(key) as reader:value=reader.read().decode()
                elif op=='delete':store.delete_object(key)
                elif op=='fixture-file':(root/key).write_text(case['Data'])
                elif op=='fixture-dir':(root/key).mkdir(parents=True,exist_ok=True)
            except OSError:ok=False
            files={str(path.relative_to(root)):path.read_text() for path in root.rglob('*') if path.is_file()}
            dirs=sorted(str(path.relative_to(root)) for path in root.rglob('*') if path.is_dir())
            python.append(dict(ok=ok,value=value,files=files,dirs=dirs))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/storage/local.go','server/tests/parity/go_local_storage/main.go',
             'server/src/workpal_backend/files/local_storage.py','server/src/workpal_backend/files/avatar_urls.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go LocalStorage upload/read/delete isolated file snapshots and success/failure; no exactOSerrorstrings, concurrency, symlink policy, HTTP or attachment authorization certification.',
        fixtures=cases,go=go,python=python,mismatches=mismatches,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        binary_sha256=hashlib.sha256((binaries/'local-storage-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),mismatches=mismatches)))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
