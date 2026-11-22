"""Fleet PAT protocol; positive identities expire in Redis after sixty seconds."""
import hashlib
import json

import httpx
from redis import Redis
from redis.exceptions import RedisError

from .profile_decode import _Object, _invalid_constant, _replace_surrogates, go_trim_space


class CloudPATInvalid(Exception):
    pass


class CloudPATUnavailable(Exception):
    pass


def decode_struct(raw, fields):
    """encoding/json struct semantics: folded keys, null scalars, duplicate errors."""
    try:
        obj = json.loads(raw.decode('utf-8', errors='replace'), object_pairs_hook=_Object,
                         parse_constant=_invalid_constant)
        result = {key: False if kind is bool else '' for key, kind in fields.items()}
        if obj is None:
            return result
        if not isinstance(obj, _Object):
            raise ValueError()
        for key, value in obj:
            folded = key.upper().replace('K', 'K')
            field = next((name for name in fields if name.upper() == folded), None)
            if field is None or value is None:
                continue
            if type(value) is not fields[field]:
                raise ValueError()
            result[field] = _replace_surrogates(value) if isinstance(value, str) else value
        return result
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CloudPATUnavailable() from exc


def marshal(value):
    # Go json.Marshal HTML escapes strings and does not append a newline.
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace(
        '&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace(
        '\u2028', '\\u2028').replace('\u2029', '\\u2029').encode()


class CloudPATVerifier:
    def __init__(self, base_url, *, client=None, settings=None):
        self.base_url = go_trim_space(base_url).rstrip('/')
        self.client = client
        self.settings = settings

    def cache(self, operation, token_hash, *args, **kwargs):
        if self.settings is None:
            return None
        try:
            with Redis.from_url(self.settings.redis_url, socket_connect_timeout=.25,
                                socket_timeout=.25, retry_on_timeout=False) as client:
                return getattr(client, operation)(
                    self.settings.redis_key_prefix + 'mul:auth:mcn:' + token_hash, *args, **kwargs)
        except (RedisError, OSError):
            return None

    def verify(self, token, lookup):
        if not self.base_url or not token:
            raise CloudPATInvalid()
        digest = hashlib.sha256(token.encode()).hexdigest()
        cached = self.cache('get', digest)
        if cached:
            try:
                identity = decode_struct(cached, {'o':str, 'i':str, 'r':str})
                if identity['o']:
                    return identity
            except CloudPATUnavailable:
                pass
        identity = self.fetch(token)
        try:
            exists = lookup(identity['o']) if lookup is not None else True
        except Exception as exc:
            raise CloudPATUnavailable() from exc
        if not exists:
            raise CloudPATInvalid()
        self.cache('set', digest, marshal(identity), ex=60)
        return identity

    def fetch(self, token):
        body = marshal({'token': token})
        if len(body) > 4096:
            raise CloudPATUnavailable()
        if self.client is None:
            with httpx.Client(timeout=5, follow_redirects=True, max_redirects=10) as client:
                return self._fetch(client, body)
        return self._fetch(self.client, body)

    def _fetch(self, client, body):
        try:
            with client.stream('POST', self.base_url + '/api/v1/pat/verify', content=body,
                               headers={'Content-Type':'application/json', 'Accept':'application/json'}) as response:
                if response.status_code != 200:
                    raise CloudPATUnavailable()
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        raise CloudPATUnavailable()
        except (httpx.HTTPError, ValueError, OSError) as exc:
            raise CloudPATUnavailable() from exc
        parsed = decode_struct(bytes(raw), {'valid':bool, 'reason':str, 'owner_id':str,
                                          'instance_id':str, 'instance_record_id':str})
        if not parsed['valid']:
            raise CloudPATInvalid()
        if not parsed['owner_id']:
            raise CloudPATUnavailable()
        return {'o':parsed['owner_id'], 'i':parsed['instance_id'], 'r':parsed['instance_record_id']}
