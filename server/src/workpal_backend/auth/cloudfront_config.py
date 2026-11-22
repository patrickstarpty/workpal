"""CloudFront initialization policy with explicit caller-owned secret access."""
import base64
import logging
from .cloudfront import CloudFrontSigner

log = logging.getLogger(__name__)


def signer_from_env(env, *, secret_loader=None):
    key_pair_id = env.get('CLOUDFRONT_KEY_PAIR_ID', '')
    if not key_pair_id:
        return None
    domain = env.get('CLOUDFRONT_DOMAIN', '')
    cookie_domain = env.get('COOKIE_DOMAIN', '')
    if not domain or not cookie_domain:
        log.error('CloudFront domain or cookie domain is not configured')
        return None
    try:
        secret = env.get('CLOUDFRONT_PRIVATE_KEY_SECRET', '')
        if secret:
            if secret_loader is None:
                raise ValueError('CloudFront secret loader is not configured')
            value = secret_loader(secret)
            if value is None:
                raise ValueError('CloudFront secret has no string value')
            pem = value.encode('utf8', 'surrogateescape')
        else:
            encoded = env.get('CLOUDFRONT_PRIVATE_KEY', '')
            if not encoded:
                raise ValueError('CloudFront private key is not configured')
            pem = base64.b64decode(encoded.replace('\r', '').replace('\n', ''), validate=True)
        return CloudFrontSigner.from_pem(pem, key_pair_id, domain, cookie_domain)
    except Exception:
        log.error('CloudFront key initialization failed')
        return None
