"""Offline CloudFront policy signing matching the Go backend protocol.

Key acquisition and deployment configuration belong to the caller. This module
never contacts AWS or reads process environment variables.
"""
import base64
import logging
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from .rsa_keys import parse_rsa_private_key

log = logging.getLogger(__name__)


def cf_base64(data):
    return base64.b64encode(data).decode().translate(str.maketrans('+=/', '-_~'))


class CloudFrontSigner:
    def __init__(self, private_key, key_pair_id, domain, cookie_domain):
        self.private_key = private_key
        self.key_pair_id = key_pair_id
        self.domain = domain
        self.cookie_domain = cookie_domain

    @classmethod
    def from_pem(cls, pem, key_pair_id, domain, cookie_domain):
        key = parse_rsa_private_key(pem)
        return cls(key, key_pair_id, domain, cookie_domain)

    def _signed_policy(self, resource, expiry_seconds):
        # Go builds the resource with fmt.Sprintf, without JSON re-escaping it.
        policy = ('{"Statement":[{"Resource":"' + resource +
                  '","Condition":{"DateLessThan":{"AWS:EpochTime":' +
                  str(expiry_seconds) + '}}}]}').encode('utf8', 'surrogateescape')
        if self.private_key.key_size < 1024:
            raise ValueError('RSA key must be at least 1024 bits')
        signature = self.private_key.sign(policy, padding.PKCS1v15(), hashes.SHA1())
        return cf_base64(policy), cf_base64(signature)

    def signed_url(self, raw_url, expiry_seconds):
        try:
            policy, signature = self._signed_policy(raw_url, expiry_seconds)
        except Exception:
            log.exception('Failed to sign CloudFront URL')
            return raw_url
        separator = '&' if '?' in raw_url else '?'
        return (raw_url + separator + 'Policy=' + policy + '&Signature=' + signature +
                '&Key-Pair-Id=' + self.key_pair_id)

    def signed_url_with_content_disposition(self, raw_url, disposition, expiry_seconds):
        from workpal_backend.infrastructure.go_url_query import set_query_value
        if disposition:
            raw_url = set_query_value(raw_url, 'response-content-disposition', disposition)
        return self.signed_url(raw_url, expiry_seconds)

    def signed_cookies(self, expiry_seconds):
        try:
            policy, signature = self._signed_policy('https://' + self.domain + '/*', expiry_seconds)
        except Exception:
            log.exception('Failed to sign CloudFront cookie policy')
            return None
        return [dict(name=name, value=value, domain=self.cookie_domain, path='/',
                     expires=expiry_seconds, secure=True, http_only=True, same_site='none')
                for name, value in [('CloudFront-Policy', policy),
                                    ('CloudFront-Signature', signature),
                                    ('CloudFront-Key-Pair-Id', self.key_pair_id)]]
