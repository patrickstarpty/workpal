"""Security policy on attachment text-preview responses."""
import re
from workpal_backend.auth.profile_decode import go_trim_space, _replace_surrogates
from workpal_backend.workspaces.decode import go_lower
from workpal_backend.realtime.origins import url_host


def normalize_frame_ancestor(raw):
    raw = go_trim_space(raw)
    match = re.match(r'([A-Za-z][A-Za-z0-9+.-]*):', raw)
    if match is None:
        return None
    scheme = match.group(1).lower()
    if scheme not in ('http', 'https'):
        return None
    try:
        host = url_host(raw)
    except ValueError:
        return None
    return scheme + '://' + go_lower(_replace_surrogates(host)) if host else None


def preview_csp(frame_ancestors):
    ancestors = ["'self'"]
    seen = set(ancestors)
    for raw in frame_ancestors:
        source = normalize_frame_ancestor(raw)
        if source is not None and source not in seen:
            seen.add(source)
            ancestors.append(source)
    return ("default-src 'none'; img-src 'self' data:; media-src 'self'; "
            'frame-ancestors ' + ' '.join(ancestors) + "; object-src 'none'; "
            "base-uri 'none'; form-action 'none'")
