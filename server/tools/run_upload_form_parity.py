"""Original parseUploadForm vs Python parser, preserving duplicate values and bytes."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.upload_form import parse_upload_form,UploadFormError

def encode(value):return base64.b64encode(value).decode()
def digest(value):return dict(size=len(value),sha256=hashlib.sha256(value).hexdigest())
async def observe(f):
    async def generated():
        if f.get('Sizes'):
            for index,size in enumerate(f['Sizes']):
                yield ('--boundary\r\nContent-Disposition: form-data; name="other"; filename="'+str(index)+'"\r\n\r\n').encode()
                remaining=size
                while remaining:
                    count=min(remaining,65536);yield b'\0'*count;remaining-=count
                yield b'\r\n'
            yield b'--boundary--\r\n'
            return
        yield ('--boundary\r\nContent-Disposition: form-data; name="'+f['Field']+'"; filename="a"\r\n\r\n').encode()
        for index,size in enumerate([f['PayloadSize'],f['MetadataSize']]):
            remaining=size
            while remaining:
                count=min(remaining,65536);yield b'\0'*count;remaining-=count
            if index==0:
                yield b'\r\n--boundary\r\nContent-Disposition: form-data; name="description"\r\n\r\n'
        yield b'\r\n--boundary--\r\n'
    body=generated() if f.get('Generate') else base64.b64decode(f['Body'])
    try:form=await parse_upload_form(body,f['ContentType'])
    except UploadFormError as error:return dict(status=error.status,limit=error.limit or 0)
    try:
        values={encode(k.encode('utf8','surrogateescape')):[digest(v.encode('utf8','surrogateescape')) for v in items] for k,items in form.values.items()}
        files={}
        for key,items in form.files.items():
            files[encode(key.encode('utf8','surrogateescape'))]=[dict(filename=encode(file.filename.encode('utf8','surrogateescape')),body=digest(await file.read()),disk=file.file._rolled) for file in items]
        return dict(status=200,values=values,files=files)
    finally:await form.close()

def run(output):
    fixtures=[]
    headers=[b'Content-Disposition: form-data; name="file"; filename="a.txt"',b'Content-Disposition: form-data; name="file"; filename=""',b'Content-Disposition: form-data; name="value"',b'Content-Disposition: form-data; filename="a.txt"',b'Content-Disposition: attachment; name="file"; filename="a.txt"',b'',b'Content-Disposition: form-data; name="file"; filename="C:\\dir\\a.txt"',b'Content-Disposition: form-data; name="file"; filename="dir/a.txt"',b'Content-Disposition: form-data; name="file"; filename="a/"',b'Content-Disposition: form-data; name="file"; filename="a"; filename="b"',b'Content-Disposition: form-data; name="file"; filename*=utf-8\'\'%E4%B8%AD.txt',b'Content-Disposition: form-data; name="file"; filename*0*=utf-8\'\'%E4; filename*1*=%B8%AD',b'Content-Disposition: form-data; name="file"; filename="a"\r\nContent-Disposition: form-data; name="other"; filename="b"',b'Content-Disposition: form-data;\r\n name="file"; filename="folded"']
    def add(body,content_type='multipart/form-data; boundary=boundary'):fixtures.append(dict(Body=encode(body),ContentType=content_type))
    for header in headers:
        for data in [b'',b'abc',b'a\xff\0b',b'a\r\n--boundaryX\r\nb']:
            body=b'--boundary\r\n'+header+b'\r\n\r\n'+data+b'\r\n--boundary--\r\n'
            add(body)
    base=b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="a"\r\n\r\nbody\r\n--boundary--\r\n'
    for prefix in [b'',b'\r\n',b'preamble\r\n',b'preamble\n']:add(prefix+base)
    for suffix in [b'',b'epilogue',b'\nextra']:add(base+suffix)
    for cut in [1,2,3,4,5,10,20]:add(base[:-cut])
    add(base.replace(b'\r\n',b'\n'))
    for content_type in ['', 'text/plain','multipart/mixed; boundary=boundary','multipart/form-data','multipart/form-data; boundary="boundary"','MULTIPART/FORM-DATA; BOUNDARY=boundary','multipart/form-data; boundary=boundary; boundary=other']:add(base,content_type)
    for value in [b'a=3Db=0A',b'a=\r\nb',b'a=ZZ',b'a=\n b',b'raw\xff',b'end=']:
        for name in [b'; name="value"',b'; name="file"; filename="a"']:
            add(b'--boundary\r\nContent-Disposition: form-data'+name+b'\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n'+value+b'\r\n--boundary--\r\n')
    add(b'--boundary--\r\n')
    add(b'--boundary\r\nContent-Disposition: form-data; name="x"\r\n\r\na\r\n--boundary\r\nContent-Disposition: form-data; name="x"\r\n\r\nb\r\n--boundary--\r\n')
    for value in [b'=',b'a\x00b',b'a  \r\nb\t',b'a'*4095,b'a'*4096,b'a'*4095+b'\n',b'a=\r',b'a=Z',b'==']:
        for name in [b'; name="value"',b'; name="file"; filename="a"']:
            add(b'--boundary\r\nContent-Disposition: form-data'+name+b'\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n'+value+b'\r\n--boundary--\r\n')
    for header in [b'X-Test : value',b'X{Test}: value',b'X-Test: a\x00b',b'X-Test: a\tb',b'X-Test: a\xffb',b'X-Test: value\r\n folded\r\n\tmore']:
        add(base.replace(b'\r\n\r\nbody',b'\r\n'+header+b'\r\n\r\nbody'))
    for count in [999,1000,1001]:
        add((b'--boundary\r\nContent-Disposition: form-data; name="x"\r\n\r\nv\r\n'*count)+b'--boundary--\r\n')
    for size,metadata,field in [(100<<20,0,'file'),((100<<20)+1,0,'file'),(100<<20,2<<20,'file'),((100<<20)+1,0,'other')]:
        fixtures.append(dict(Body='',ContentType='multipart/form-data; boundary=boundary',Generate=True,PayloadSize=size,MetadataSize=metadata,Field=field))
    for sizes in [[60<<20,(40<<20)+1,1],[100<<20,1,0]]:
        fixtures.append(dict(Body='',ContentType='multipart/form-data; boundary=boundary',Generate=True,Sizes=sizes))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_upload_form"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_upload_form.go && cd /work && go build -mod=readonly -p=4 -o /out/upload-form-oracle ./parity'])
    # Each request owns its form and temporary files. Isolate bounded batches
    # without changing the pinned target or dropping any fixture.
    go=[]
    batches=[[fixture] for fixture in fixtures]
    for batch in batches:
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
            '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
            '/out/upload-form-oracle'],input=json.dumps(batch))
        go.extend(json.loads(result.stdout))
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file_upload_limits.go','server/tests/parity/go_upload_form/main.go','server/tests/parity/go_upload_form/wrapper.go','server/src/workpal_backend/files/upload_form.py','server/src/workpal_backend/files/mime_parameters.py','server/src/workpal_backend/files/form_values.py','server/src/workpal_backend/files/multipart_framing.py','server/src/workpal_backend/files/quoted_printable.py','server/tools/run_upload_form_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original parseUploadForm vs Python upload parser: parse status, duplicate field/file arrays, filename bytes and SHA256/length of each decoded body. Includes selected MIME/boundary/quoted-printable fixtures,1000part limit, real100MiB file/101MiB body boundaries and oversized non-file-named uploads. Includes multi-file cumulative memory-to-disk selection. Temp-file failure/lifecycle and complete metadata memory-budget and request transport not certified.',fixtures=fixtures,execution_batch_sizes=[len(batch) for batch in batches],go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
