"""Pinned Go multipart Request.FormValue precedence versus Python."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.form_values import form_value
from workpal_backend.files.upload_form import UploadForm,parse_upload_form,UploadFormError

def run(output):
    queries=['','issue_id=query&issue_id=second','issue_id=&issue_id=second','issue_id','issue_id=bad%zz&issue_id=valid','issue_id=bad;ignored&other=x','issue%5fid=hello+world','issue_id=%ff']
    queries.extend('issue_id=%'+f'{n:02X}' for n in range(256))
    fixtures=[dict(Query=q,Name=name,Values=values) for q in queries for name in ['issue_id','absent'] for values in [[],['multipart-first','multipart-second']]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_upload_form_values"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/upload-form-values-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
            '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
            '/out/upload-form-values-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    async def observe(f):
        body=b''.join(b'--boundary\r\nContent-Disposition: form-data; name="issue_id"\r\n\r\n'+v.encode()+b'\r\n' for v in f['Values'])+b'--boundary--\r\n'
        parse_error=False
        try:form=await parse_upload_form(body,'multipart/form-data; boundary=boundary',raw_query=f['Query'].encode())
        except UploadFormError:parse_error=True
        else:await form.close()
        value=form_value(UploadForm({'issue_id':f['Values']},{}),f['Name'],f['Query'].encode())
        return dict(parse_error=parse_error,value=base64.b64encode(value.encode('utf8','surrogateescape')).decode())
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/tests/parity/go_upload_form_values/main.go','server/src/workpal_backend/files/form_values.py','server/src/workpal_backend/files/upload_form.py','server/tools/run_upload_form_values_parity.py']
    stdlib=command(['docker','run','--rm','--network','none','golang:1.26.9','sha256sum','/usr/local/go/src/net/http/request.go']).stdout.split()[0]
    Path(output).write_text(json.dumps(dict(scope='Pinned Go1.26.9 Request.FormValue after actual ParseMultipartForm: query precedence, empty/duplicate values, malformed query components, byte-valued fields. Not full upload handler certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,stdlib_sha256=stdlib,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
