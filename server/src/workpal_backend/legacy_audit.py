"""Read-only preflight. Missing rows have no provable deletion provenance."""
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from .legacy_import import _read_source, _mapped_body, _object, _invalid_constant, _uuid


def _json(raw):
    return json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_constant)


def _audit(source, target, expected_checksum=None):
    rows, _, _, checksum, source_id = _read_source(Path(source).resolve())
    with closing(sqlite3.connect(Path(target).resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN')
        manifest = conn.execute('SELECT * FROM legacy_imports WHERE source_id=?', (source_id,)).fetchone()
        if manifest is None:
            return dict(ok=False, source_checksum=checksum, error='missing manifest')
        mapping = _json(manifest['mapping'])
        counts = dict(Counter(r['kind'] for r in rows))
        errors = []
        wid = _uuid('workspaces', next(r['id'] for r in rows if r['kind'] == 'workspaces'))
        if manifest['workspace_id'] != wid:
            errors.append('manifest workspace')
        manifest_counts = _json(manifest['counts'])
        if not isinstance(manifest_counts, dict) or any(type(v) is not int or v < 0 for v in manifest_counts.values()) or manifest_counts != counts:
            errors.append('manifest counts')
        user_rows = [r for r in rows if r['kind'] == 'users']
        if not isinstance(mapping, dict) or set(mapping) != {'users', 'members', 'workspaces'}:
            raise ValueError('invalid mapping')
        expected_users = {}
        for row in user_rows:
            uid = _uuid('users', row['id'])
            if mapping['users'].get(row['id']) == manifest['owner_id']:
                uid = manifest['owner_id']
            if uid == manifest['owner_id'] and uid != _uuid('users', row['id']):
                native = conn.execute('SELECT email FROM users WHERE id=?', (uid,)).fetchone()
                if native is None or native['email'] != row['body']['email'].strip().lower():
                    errors.append('mapped owner identity')
            expected_users[row['id']] = uid
        if mapping != {'users': expected_users, 'members': expected_users, 'workspaces': {next(r['id'] for r in rows if r['kind']=='workspaces'): wid}}:
            errors.append('manifest mapping')
        if not conn.execute('SELECT 1 FROM workspaces WHERE id=?', (wid,)).fetchone():
            errors.append('native workspace')
        for uid in set(expected_users.values()) | {manifest['owner_id']}:
            if not conn.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone():
                errors.append('native user')
            member = conn.execute('SELECT id,role FROM members WHERE workspace_id=? AND user_id=?', (wid, uid)).fetchall()
            if len(member) != 1 or member[0]['role'] not in {'owner', 'admin', 'member'}:
                errors.append('native membership')
            elif uid in expected_users.values() and member[0]['id'] != uid:
                errors.append('member identity')
        if not conn.execute("SELECT 1 FROM members WHERE workspace_id=? AND role='owner'", (wid,)).fetchone():
            errors.append('workspace ownership')
        actual = {(r['kind'], r['id']): r for r in conn.execute('SELECT * FROM workspace_records WHERE workspace_id=?', (manifest['workspace_id'],))}
        missing, raw_diff, edits = [], [], []
        for row in rows:
            key = (row['kind'], row['id'])
            found = actual.get(key)
            if found is None:
                missing.append(list(key))
                continue
            if found['position'] != row['position']:
                errors.append('source position')
            if found['source_body'] != row['source_body']:
                raw_diff.append(list(key))
            expected = _mapped_body(row['body'], mapping)
            if row['kind'] in {'users', 'workspaces'}:
                expected['id'] = mapping[row['kind']][row['id']]
            if row['kind'] == 'preferences' and not expected.get('user_id') and len(user_rows) == 1:
                expected['user_id'] = next(iter(expected_users.values()))
            if not isinstance(_json(found['body']), dict):
                raise ValueError('invalid current body')
            if _json(found['body']) != expected:
                edits.append(list(key))
        changed = manifest['source_checksum'] != checksum
        baseline_changed = expected_checksum is not None and checksum != expected_checksum
        return dict(ok=not (missing or raw_diff or changed or errors or baseline_changed), preflight_only=True,
                    source_checksum=checksum, manifest_checksum=manifest['source_checksum'],
                    source_changed=changed, baseline_changed=baseline_changed, integrity_errors=errors, source_count=len(rows), target_count=len(actual),
                    counts=dict(Counter(r['kind'] for r in rows)), mapping=mapping,
                    missing_unknown_reason=missing, source_body_differences=raw_diff,
                    current_body_changes=edits)


def audit(source, target, *, expected_checksum=None):
    """Read-only snapshot validation; never attests that writers are stopped."""
    try:
        return _audit(source, target, expected_checksum)
    except (ValueError, TypeError, KeyError, sqlite3.Error, RecursionError):
        return dict(ok=False, preflight_only=True, error='Invalid or unsupported audit data')
