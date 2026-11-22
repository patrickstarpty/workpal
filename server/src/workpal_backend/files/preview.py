"""Canonical attachment text-preview whitelist, packaged for Python execution."""
from importlib.resources import files
import json
import posixpath
from workpal_backend.auth.profile_decode import go_trim_space
from workpal_backend.workspaces.decode import go_lower

_RULES = json.loads(files(__package__).joinpath('attachment_text_preview.json').read_text())
_PREFIXES = tuple(_RULES['content_type_prefixes'])
_TYPES = frozenset(_RULES['content_types'])
_EXTENSIONS = frozenset(_RULES['extensions'])
_BASENAMES = frozenset(_RULES['basenames'])


def is_text_previewable(content_type, filename):
    content_type = go_lower(go_trim_space(content_type))
    content_type = go_trim_space(content_type.split(';', 1)[0])
    if content_type.startswith(_PREFIXES) or content_type in _TYPES:
        return True
    # Go path.Base first strips trailing slashes; unlike path.Clean it does not
    # resolve preceding dot segments. Backslashes are separators only here.
    base = go_lower(filename.replace('\\', '/').rstrip('/').rsplit('/', 1)[-1])
    if not base:
        base = '/' if filename else '.'
    dot = base.rfind('.')
    extension = base[dot + 1:] if dot >= 0 else ''
    return bool(extension and extension in _EXTENSIONS) or base in _BASENAMES
