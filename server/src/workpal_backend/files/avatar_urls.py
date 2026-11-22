"""Avatar URL capabilities and storage policy from Go handler/avatar.go.

Pure policy: callers provide their actual storage adapter and attachment lookup.
No network fetches and no access to the legacy upload directory.
"""
import base64
import hashlib
import hmac
import posixpath
import re
from urllib.parse import urlsplit,unquote
from workpal_backend.auth.profile_decode import go_trim_space
from workpal_backend.infrastructure.go_uuid import parse_uuid

PREFIX='/api/avatars/'
TYPES={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif',
       '.webp':'image/webp','.avif':'image/avif','.bmp':'image/bmp','.ico':'image/x-icon'}


def extension(key):
    base=key.rsplit('/',1)[-1]
    dot=base.rfind('.')
    return base[dot:] if dot>=0 else ''


def content_type(key):return TYPES.get(extension(key).lower(),'')


def redirect_max_age(ttl_seconds):
    if ttl_seconds<=0:ttl_seconds=1800
    return min(60,int(int(ttl_seconds)/2))


class LocalObjectURLs:
    """LocalStorage URL operations, independent of file reads/writes."""
    is_local=True

    def __init__(self,base_url=''):
        self.base_url=base_url.removesuffix('/')

    def object_url(self,key):return self.base_url+'/uploads/'+key

    def key_from_url(self,raw):
        if self.base_url and raw.startswith(self.base_url):raw=raw[len(self.base_url):]
        index=raw.find('/uploads/')
        return raw[index+len('/uploads/'):] if index>=0 else raw.rsplit('/',1)[-1]


class AvatarURLs:
    def __init__(self,secret,storage=None,public_url='',publicly_readable=lambda url:False):
        self.signing_key=hashlib.sha256(b'avatar-url:'+secret.encode()).digest()
        self.storage=storage
        self.public_url=public_url.rstrip('/')
        self.publicly_readable=publicly_readable

    def sign(self,key):
        return base64.urlsafe_b64encode(hmac.digest(self.signing_key,key.encode(),'sha256')).rstrip(b'=').decode()

    def valid(self,key,signature):return hmac.compare_digest(signature.encode(),self.sign(key).encode())

    def path(self,key):return PREFIX+self.sign(key)+'/'+key

    def key_from_served(self,raw):
        rest=raw
        if not raw.startswith('/'):
            try:
                if any(ord(c)<32 or ord(c)==127 for c in raw):return None
                parsed=urlsplit(raw)
                if re.search(r'%(?![0-9a-fA-F]{2})',parsed.path):return None
                rest=unquote(parsed.path,errors='strict')
            except (ValueError,UnicodeError):return None
        if not rest.startswith(PREFIX):return None
        signature,separator,key=rest[len(PREFIX):].partition('/')
        return key if separator and key and self.valid(key,signature) else None

    def owned_key(self,raw):
        key=self.storage.key_from_url(raw)
        return key if key and key!=raw and self.storage.object_url(key)==raw else ''

    def resolve(self,raw):
        if not raw or self.storage is None:return raw
        key=self.key_from_served(raw)
        if key is not None:return self.public_url+self.path(key)
        key=self.owned_key(raw)
        if not key or not content_type(key):return raw
        if not self.storage.is_local and self.publicly_readable(raw):return raw
        return self.public_url+self.path(key)

    def normalize(self,raw):
        if self.storage is None:return raw
        key=self.key_from_served(raw)
        return self.storage.object_url(key) if key is not None else raw

    def publishable(self,key,lookup_attachment):
        if not content_type(key):return False
        if not key.startswith('workspaces/'):return True
        base=posixpath.basename(posixpath.normpath(key))
        ext=extension(base)
        try:aid=parse_uuid(base[:-len(ext)] if ext else base)
        except ValueError:return False
        try:attachment=lookup_attachment(aid)
        except Exception:return False
        if attachment is None or not attachment['content_type'].lower().startswith('image/'):return False
        return not any(attachment.get(k) is not None for k in ('issue_id','comment_id','chat_session_id','chat_message_id','task_id'))

    def accept(self,raw,current,lookup_attachment):
        value=self.normalize(go_trim_space(raw))
        if self.storage is None or value==go_trim_space(current):return value
        key=self.owned_key(value)
        if not key or self.publishable(key,lookup_attachment):return value
        raise ValueError('avatar_url must reference a standalone image upload, not a file attached to an issue, comment, or chat')
