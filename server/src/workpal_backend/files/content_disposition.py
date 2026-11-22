"""Go storage media disposition and RFC 5987 filename encoding."""
from urllib.parse import quote
from workpal_backend.auth.profile_decode import go_trim_space, _replace_surrogates
from workpal_backend.workspaces.decode import go_lower


def is_inline_content_type(content_type):
    media = go_lower(go_trim_space(content_type))
    media = go_trim_space(media.split(';', 1)[0])
    if media == 'image/svg+xml':
        return False
    return media.startswith(('image/', 'video/', 'audio/')) or media == 'application/pdf'


def _sanitize(filename):
    return ''.join('_' if ord(char) < 32 or ord(char) == 127 or char in '\";\\' else char
                   for char in filename)


def content_disposition(content_type, filename, *, force_attachment=False):
    mode = 'inline' if not force_attachment and is_inline_content_type(content_type) else 'attachment'
    filename = _replace_surrogates(filename)
    if filename.isascii():
        return mode + '; filename="' + _sanitize(filename) + '"'
    fallback = ''.join(char if ord(char) < 128 else '_' for char in filename)
    encoded = quote(filename, safe='!#$&+-.^_`|~', encoding='utf-8', errors='strict')
    return mode + '; filename="' + _sanitize(fallback) + '"; filename*=UTF-8\'\'' + encoded
