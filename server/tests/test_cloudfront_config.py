import base64
from pathlib import Path
import pytest

KEY=(Path(__file__).parent/'fixtures/cloudfront-test-key.pem').read_bytes()
BASE={'CLOUDFRONT_KEY_PAIR_ID':'K-test','CLOUDFRONT_DOMAIN':'cdn.test','COOKIE_DOMAIN':'.test','CLOUDFRONT_PRIVATE_KEY':base64.b64encode(KEY).decode()}


@pytest.mark.parametrize('missing',['CLOUDFRONT_KEY_PAIR_ID','CLOUDFRONT_DOMAIN','COOKIE_DOMAIN'])
def test_missing_configuration_does_not_acquire_keys(missing):
    from workpal_backend.auth.cloudfront_config import signer_from_env
    env={**BASE,'CLOUDFRONT_PRIVATE_KEY_SECRET':'fixture-secret',missing:''}
    calls=[]
    def forbidden(name):calls.append(name);return KEY.decode()
    assert signer_from_env(env,secret_loader=forbidden) is None
    assert calls==[]


def test_secret_has_priority_and_failure_does_not_fall_back():
    from workpal_backend.auth.cloudfront_config import signer_from_env
    calls=[]
    env={**BASE,'CLOUDFRONT_PRIVATE_KEY_SECRET':'fixture-secret','CLOUDFRONT_PRIVATE_KEY':'invalid'}
    def load(name):calls.append(name);return KEY.decode()
    assert signer_from_env(env,secret_loader=load) is not None
    assert calls==['fixture-secret']
    def fail(name):raise RuntimeError('fixture unavailable')
    assert signer_from_env({**BASE,'CLOUDFRONT_PRIVATE_KEY_SECRET':'fixture-secret'},secret_loader=fail) is None
    assert signer_from_env({**BASE,'CLOUDFRONT_PRIVATE_KEY_SECRET':'fixture-secret'},secret_loader=lambda name:None) is None


@pytest.mark.parametrize(('transform','valid'),[
    (lambda value:value,True),
    (lambda value:value[:20]+'\r\n'+value[20:],True),
    (lambda value:value[:20]+' '+value[20:],False),
    (lambda value:value[:20]+'\t'+value[20:],False),
    (lambda value:'',False),
])
def test_env_key_base64_matches_go(transform,valid):
    from workpal_backend.auth.cloudfront_config import signer_from_env
    env={**BASE,'CLOUDFRONT_PRIVATE_KEY':transform(BASE['CLOUDFRONT_PRIVATE_KEY'])}
    assert (signer_from_env(env) is not None)==valid
