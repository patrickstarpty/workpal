"""Request.FormValue precedence after multipart parsing (Go net/http)."""
import re
from urllib.parse import unquote_to_bytes


def form_value(form, name, raw_query=b''):
    key = name.encode('utf8', 'surrogateescape')
    for component in raw_query.split(b'&'):
        if b';' in component:
            continue
        candidate, _, value = component.partition(b'=')
        if re.search(br'%(?![0-9a-fA-F]{2})', candidate + b'&' + value):
            continue
        if unquote_to_bytes(candidate.replace(b'+', b' ')) == key:
            return unquote_to_bytes(value.replace(b'+', b' ')).decode('utf8', 'surrogateescape')
    return form.value(name)


def query_is_invalid(raw_query):
    return b';' in raw_query or re.search(br'%(?![0-9a-fA-F]{2})', raw_query) is not None
