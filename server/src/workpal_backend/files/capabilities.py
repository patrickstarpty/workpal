"""Single-attachment download capabilities compatible with the Go signer."""
import hashlib
import hmac
import re
import time
from .ranges import _int64


class AttachmentCapabilities:
    def __init__(self, secret):
        self._key = hashlib.sha256(b'attachment-download-capability:' + secret.encode('utf8', 'surrogateescape')).digest()

    def sign(self, attachment_id, expires, intent=''):
        message = f'v1|{attachment_id}|{expires}'
        if intent:
            message += '|' + intent
        return hmac.digest(self._key, message.encode('utf8', 'surrogateescape'), 'sha256').hex()

    def path(self, attachment_id, *, now_ns=None, download=False):
        now_ns = time.time_ns() if now_ns is None else now_ns
        expires = (now_ns + 60_000_000_000) // 1_000_000_000
        signature = self.sign(attachment_id, expires, 'attachment' if download else '')
        value = f'/api/attachments/{attachment_id}/signed-download?exp={expires}&sig={signature}'
        return value + '&dl=1' if download else value

    def verify(self, attachment_id, raw_expiry, signature, *, intent='', now_ns=None):
        if not attachment_id or not raw_expiry or not signature:
            return False
        try:
            expires = _int64(raw_expiry)
        except ValueError:
            return False
        now_ns = time.time_ns() if now_ns is None else now_ns
        if now_ns // 1_000_000_000 > expires:
            return False
        # bytes.fromhex accepts whitespace; Go hex.DecodeString does not.
        if len(signature) % 2 or re.fullmatch(r'[0-9a-fA-F]+', signature) is None:
            return False
        return hmac.compare_digest(bytes.fromhex(signature), bytes.fromhex(self.sign(attachment_id, expires, intent)))
