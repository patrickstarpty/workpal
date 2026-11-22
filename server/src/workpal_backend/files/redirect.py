"""Go http.Redirect's 302 response used by attachment download signers."""
import re
from starlette.responses import Response
from ..realtime.origins import url_host


def _clean(path):
    rooted = path.startswith('/')
    parts = []
    for part in path.split('/'):
        if part in ('', '.'):
            continue
        if part == '..' and parts and parts[-1] != '..':
            parts.pop()
        elif part != '..' or not rooted:
            parts.append(part)
    return ('/' if rooted else '') + '/'.join(parts) or '.'


def download_redirect(target, *, request_path='/', method='GET', headers=None):
    try:
        host = url_host(target)
        relative = not host and not re.match(r'[A-Za-z][A-Za-z0-9+.-]*:', target)
    except ValueError:
        relative = False
    if relative:
        if not target.startswith('/'):
            oldpath = request_path or '/'
            target = oldpath[:oldpath.rfind('/') + 1] + target
        path, mark, query = target.partition('?')
        trailing = path.endswith('/')
        target = _clean(path)
        if trailing and not target.endswith('/'):
            target += '/'
        target += mark + query
    result = {key.lower(): value for key, value in (headers or {}).items()}
    had_content_type = 'content-type' in result
    result['location'] = ''.join(chr(byte) if byte < 128 else f'%{byte:02x}'
                                 for byte in target.encode('utf8', 'surrogateescape'))
    body = b''
    if not had_content_type and method in ('GET', 'HEAD'):
        result['content-type'] = 'text/html; charset=utf-8'
    if not had_content_type and method == 'GET':
        escaped = target.translate(str.maketrans({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&#34;', "'":'&#39;'}))
        body = ('<a href="' + escaped + '">Found</a>.\n\n').encode('utf8', 'surrogateescape')
    return Response(body, status_code=302, headers=result)
