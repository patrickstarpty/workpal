import base64
from pathlib import Path
import pytest

KEY=Path(__file__).parent/'fixtures/cloudfront-test-key.pem'


def decode(value):return base64.b64decode(value.translate(str.maketrans('-_~','+=/')))


@pytest.mark.parametrize('raw',['https://cdn.test/a','https://cdn.test/a?x=1','https://cdn.test/a#fragment','https://cdn.test/a"b',''])
def test_signed_url_preserves_original_resource_and_signature(raw):
    from workpal_backend.auth.cloudfront import CloudFrontSigner
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    signer=CloudFrontSigner.from_pem(KEY.read_bytes(),'K-test','cdn.test','.example.test')
    result=signer.signed_url(raw,1700000000)
    prefix=raw+('&' if '?' in raw else '?')
    assert result.startswith(prefix+'Policy=')
    fields=dict(part.split('=',1) for part in result[len(prefix):].split('&'))
    policy=decode(fields['Policy'])
    assert policy==('{"Statement":[{"Resource":"'+raw+'","Condition":{"DateLessThan":{"AWS:EpochTime":1700000000}}}]}').encode()
    assert fields['Key-Pair-Id']=='K-test'
    signer.private_key.public_key().verify(decode(fields['Signature']),policy,padding.PKCS1v15(),hashes.SHA1())


def test_cookie_policy_has_wildcard_resource_and_required_attributes():
    from workpal_backend.auth.cloudfront import CloudFrontSigner
    signer=CloudFrontSigner.from_pem(KEY.read_bytes(),'K-test','cdn.test','.example.test')
    cookies=signer.signed_cookies(-1)
    assert [c['name'] for c in cookies]==['CloudFront-Policy','CloudFront-Signature','CloudFront-Key-Pair-Id']
    assert b'"Resource":"https://cdn.test/*"' in decode(cookies[0]['value'])
    for cookie in cookies:
        assert cookie['domain']=='.example.test'
        assert cookie['path']=='/' and cookie['expires']==-1
        assert cookie['secure'] and cookie['http_only'] and cookie['same_site']=='none'


def test_signing_failure_retains_original_url_and_returns_no_cookies():
    from workpal_backend.auth.cloudfront import CloudFrontSigner
    class BrokenKey:
        def sign(self,*args):raise ValueError('sign failure')
    signer=CloudFrontSigner(BrokenKey(),'K-test','cdn.test','.example.test')
    assert signer.signed_url('https://cdn.test/a',1)=='https://cdn.test/a'
    assert signer.signed_cookies(1) is None


def test_download_disposition_is_part_of_signed_resource():
    from workpal_backend.auth.cloudfront import CloudFrontSigner
    signer=CloudFrontSigner.from_pem(KEY.read_bytes(),'K-test','cdn.test','.example.test')
    raw='https://cdn.test/a?z=1'
    result=signer.signed_url_with_content_disposition(raw,'attachment; filename="a b.txt"',123)
    expected='https://cdn.test/a?response-content-disposition=attachment%3B+filename%3D%22a+b.txt%22&z=1'
    assert result==signer.signed_url(expected,123)
    assert signer.signed_url_with_content_disposition(raw,'',123)==signer.signed_url(raw,123)
    invalid='https://cdn.test/%zz'
    assert signer.signed_url_with_content_disposition(invalid,'attachment',123)==signer.signed_url(invalid,123)


def test_signer_key_loading_ignores_pem_label_like_go():
    from workpal_backend.auth.cloudfront import CloudFrontSigner
    pem=KEY.read_bytes().replace(b'PRIVATE KEY',b'UNRELATED LABEL')
    signer=CloudFrontSigner.from_pem(pem,'K-test','cdn.test','.example.test')
    assert 'Signature=' in signer.signed_url('https://cdn.test/a',1)
