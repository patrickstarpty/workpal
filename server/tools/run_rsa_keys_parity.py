"""Original Go RSA key parser versus Python using public disposable fixtures."""
from pathlib import Path
import base64,hashlib,json,sys,subprocess
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.auth.rsa_keys import parse_rsa_private_key

def run(output):
    pem=(ROOT/'server/tests/fixtures/cloudfront-test-key.pem').read_bytes()
    key=serialization.load_pem_private_key(pem,password=None)
    pkcs1=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption())
    nonrsa=ed25519.Ed25519PrivateKey.from_private_bytes(bytes(32)).private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    raw=[b'',b'garbage',pem,pkcs1,nonrsa,key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)]
    for base,label in [(pem,b'PRIVATE KEY'),(pkcs1,b'RSA PRIVATE KEY')]:
        begin=b'-----BEGIN '+label+b'-----\n';end=b'-----END '+label+b'-----'
        raw.extend([base.replace(label,b'UNRELATED LABEL'),b'ignored\n'+base+b'ignored',b'ignored'+base,begin+base,base.replace(begin,begin+b'Note: value\n\n'),base.replace(begin,begin+b'Note: value\n'),base.replace(b'\n',b'\r\n'),base.replace(b'\n',b' \t\n'),base.replace(end,end+b' trailing'),base.replace(end,end+b' \t'),base.replace(end,b'-----END WRONG-----'),base[:-1],base[:-10]])
        for byte in [0,9,10,13,32,58,127,255]:
            raw.append(base.replace(begin,begin+bytes([byte])))
        for cut in [0,1,8,32,len(base)//2,len(base)-1]:raw.append(base[:cut]+pem)
    raw.extend([b'-----BEGIN BAD-----\ninvalid!!\n-----END BAD-----\n'+pem,b'-----BEGIN BAD-----\nAAAA\n-----END BAD-----\n'+pem,nonrsa+pem])
    fixtures=[base64.b64encode(v).decode() for v in raw]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_rsa_keys"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/auth/parity_rsa_keys.go && cd /work && go build -mod=readonly -p=4 -o /out/rsa-keys-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{ROOT/"server/tests/fixtures"}:/fixtures:ro','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/rsa-keys-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for value in raw:
        try:key=parse_rsa_private_key(value)
        except Exception:python.append(None)
        else:
            public=key.public_key().public_numbers()
            python.append(dict(n=format(public.n,'x'),e=public.e,bits=key.key_size))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/auth/cloudfront.go','server/tests/parity/go_rsa_keys/main.go','server/tests/parity/go_rsa_keys/wrapper.go','server/src/workpal_backend/auth/rsa_keys.py','server/tests/fixtures/cloudfront-test-key.pem','server/tools/run_rsa_keys_parity.py','server/pyproject.toml','server/uv.lock']
    stdlib=command(['docker','run','--rm','--network','none','golang:1.26.9','sha256sum','/usr/local/go/src/encoding/pem/pem.go']).stdout
    Path(output).write_text(json.dumps(dict(scope='Original parseRSAPrivateKey: acceptance and public key identity for selected PKCS8/PKCS1 PEM framing/labels/headers/truncation/concatenation and non-RSA inputs. Only public disposable fixture keys. Does not certify exact ASN.1 error text, all DER encodings or environment secret resolution.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,stdlib_sha256=stdlib,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
