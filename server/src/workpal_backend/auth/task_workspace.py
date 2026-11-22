"""Go task_token_workspace.go target checks, before binding overwrites selectors."""
import re
from urllib.parse import unquote_to_bytes
from fastapi import HTTPException
from workpal_backend.infrastructure.go_uuid import parse_uuid

MISMATCH = 'task token is bound to a different workspace'


def query_values(raw):
    # Go url.ParseQuery returns an error for malformed escapes or raw semicolons,
    # including unrelated parameters. Starlette's permissive parser does not.
    if b';' in raw or re.search(rb'%(?![0-9a-fA-F]{2})', raw):
        raise HTTPException(400, 'malformed query string')
    result = {}
    for pair in raw.split(b'&'):
        if not pair:
            continue
        key, _, value = pair.partition(b'=')
        def decode(part):
            return unquote_to_bytes(part.replace(b'+', b' ')).decode('utf-8', errors='surrogateescape')
        result.setdefault(decode(key), []).append(decode(value))
    return result


def check_target(request, bound_workspace_id, resolve_slug):
    """Validate every explicit selector; callback returns canonical UUID or None.

    No mutation, network, implicit first-value selection or fallback on lookup
    failure. Request-body/path bindings belong to the later route middleware.
    """
    query = query_values(request.scope.get('query_string', b''))
    for values in (request.headers.getlist('x-workspace-id'), query.get('workspace_id', [])):
        for value in values:
            if not value:
                continue
            try:
                canonical = parse_uuid(value)
            except ValueError as exc:
                raise HTTPException(400, 'invalid workspace_id') from exc
            if canonical != bound_workspace_id:
                raise HTTPException(403, MISMATCH)
    resolved = {}
    for values in (request.headers.getlist('x-workspace-slug'), query.get('workspace_slug', [])):
        for slug in values:
            if not slug:
                continue
            if slug not in resolved:
                try:
                    target = resolve_slug(slug)
                except Exception as exc:
                    raise HTTPException(500, 'failed to resolve workspace') from exc
                if target is None:
                    raise HTTPException(404, 'workspace not found')
                resolved[slug] = target
            if resolved[slug] != bound_workspace_id:
                raise HTTPException(403, MISMATCH)
