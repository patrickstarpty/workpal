"""Original CloudFront environment initialization with isolated test keys."""
from pathlib import Path
import base64,hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.auth.cloudfront_config import signer_from_env

def run(output):
    encoded=base64.b64encode((ROOT/'server/tests/fixtures/cloudfront-test-key.pem').read_bytes()).decode()
    base=dict(CLOUDFRONT_KEY_PAIR_ID='K-test',CLOUDFRONT_DOMAIN='cdn.test',COOKIE_DOMAIN='.test',CLOUDFRONT_PRIVATE_KEY=encoded)
    fixtures=[{},base]
    for key in ['CLOUDFRONT_KEY_PAIR_ID','CLOUDFRONT_DOMAIN','COOKIE_DOMAIN']:
        for value in ['', ' ', 'fixture']:
            fixtures.append({**base,key:value})
    for value in ['', 'invalid',encoded[:20]+'\r\n'+encoded[20:],encoded[:20]+' '+encoded[20:],encoded[:20]+'\t'+encoded[20:],encoded[:-1],base64.b64encode(b'garbage').decode()]:
        fixtures.append({**base,'CLOUDFRONT_PRIVATE_KEY':value})
    # No AWS region or credentials, IMDS disabled and container network none:
    # secret mode must fail initialization rather than use the valid env key.
    fixtures.append({**base,'CLOUDFRONT_PRIVATE_KEY_SECRET':'public-test-missing-secret'})
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_cloudfront_config"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/auth/parity_cloudfront_config.go && cd /work && go build -mod=readonly -p=4 -o /out/cloudfront-config-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{ROOT/"server/tests/fixtures"}:/fixtures:ro','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/cloudfront-config-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for fixture in fixtures:
        signer=signer_from_env(fixture)
        python.append(signer.signed_url('https://cdn.test/a',1700000000) if signer is not None else None)
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/auth/cloudfront.go','server/tests/parity/go_cloudfront_config/main.go','server/tests/parity/go_cloudfront_config/wrapper.go','server/src/workpal_backend/auth/cloudfront_config.py','server/src/workpal_backend/auth/cloudfront.py','server/src/workpal_backend/auth/rsa_keys.py','server/tests/fixtures/cloudfront-test-key.pem','server/tools/run_cloudfront_config_parity.py','server/pyproject.toml','server/uv.lock']
    Path(output).write_text(json.dumps(dict(scope='Original NewCloudFrontSignerFromEnv vs Python initialization outcome and exact test-resource signature: missing fields, whitespace, base64 failure/newlines and no fallback when secret mode cannot initialize. Network none, no AWS credentials/region and IMDS disabled. Does not certify successful AWS Secrets Manager acquisition or app startup wiring.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
