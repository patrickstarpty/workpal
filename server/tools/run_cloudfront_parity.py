"""Offline byte-exact CloudFront URL/cookie policy and RSA signatures."""
from pathlib import Path
import hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.auth.cloudfront import CloudFrontSigner

def run(output):
    fixtures=[dict(URL=url,KeyPairID=key,Domain=domain,CookieDomain=cookie,Expiry=expiry) for url in ['', 'https://cdn.test/a','https://cdn.test/a?x=1','https://cdn.test/a#fragment','https://cdn.test/a"b','https://cdn.test/中文','https://cdn.test/a?Signature=old'] for expiry in [-1,0,1,1700000000,(1<<63)-1,-(1<<63)] for key,domain,cookie in [('K-test','cdn.test','.example.test'),('key &raw','cdn.test/path','localhost'),('','','')]]
    urls=['https://cdn.test/a?z=2&a=1&a=3','https://cdn.test/a?bad=%zz&x=1;ignored','HTTPS://cdn.test/a%2fb#part','https:/a','https://cdn.test/中文','https://user:p:a@cdn.test/a','https://cdn.test/a%zz','http:opaque%zz','//cdn.test/a','relative path#f f','https://[fe80::1%25eth0]/a','https://%ff.test/a','https://cdn.test/a!b[]','http:///a','https://cdn.test/a?response-content-disposition=old','https://cdn.test/a#one#two']
    fixtures.extend(dict(URL=url,Disposition=disposition,KeyPairID='K-test',Domain='cdn.test',CookieDomain='.test',Expiry=1700000000) for url in urls for disposition in ['','attachment; filename="a b.txt"','attachment; filename="中文.txt"'])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_cloudfront"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/auth/parity_cloudfront.go && cd /work && go build -mod=readonly -p=4 -o /out/cloudfront-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{ROOT/"server/tests/fixtures"}:/fixtures:ro','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/cloudfront-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    pem=(ROOT/'server/tests/fixtures/cloudfront-test-key.pem').read_bytes()
    python=[]
    for f in fixtures:
        signer=CloudFrontSigner.from_pem(pem,f['KeyPairID'],f['Domain'],f['CookieDomain'])
        python.append(dict(download=signer.signed_url_with_content_disposition(f['URL'],f.get('Disposition',''),f['Expiry']),url=signer.signed_url(f['URL'],f['Expiry']),cookies=signer.signed_cookies(f['Expiry'])))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/auth/cloudfront.go','server/tests/parity/go_cloudfront/main.go','server/tests/parity/go_cloudfront/wrapper.go','server/src/workpal_backend/auth/cloudfront.py','server/src/workpal_backend/auth/rsa_keys.py','server/src/workpal_backend/infrastructure/go_url_query.py','server/src/workpal_backend/realtime/origins.py','server/tests/fixtures/cloudfront-test-key.pem','server/tools/run_cloudfront_parity.py','server/pyproject.toml','server/uv.lock']
    Path(output).write_text(json.dumps(dict(scope='Original Go SignedURL/SignedCookies against Python with public disposable RSA2048 test key: exact policy bytes/base64/signature/URL, cookie attributes and int64 expiry. No AWS calls, environment key resolution, malformed PEM, cookie header serialization or exhaustive URL grammar certification. Includes selected content-disposition URL reconstruction/signing.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
