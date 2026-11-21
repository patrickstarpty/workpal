"""Explicit, transactional import of the former local Node SQLite store.

The source is read only. Importing never migrates a database, creates a login,
or updates existing rows. A manifest makes identical retries a no-op and rejects
changed snapshots. Raw JSON is retained alongside the active mapped content.
"""
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine, or_, select

from workpal_backend.auth.models import users
from workpal_backend.workspaces.models import issue_status, members, workspaces
from workpal_backend.workspaces.service import STATUSES
from workpal_backend.workspace_content.models import legacy_imports, records


def _uuid(kind, source_id):
    return str(uuid5(NAMESPACE_URL, f'https://workpal.local/legacy-node/{kind}/{source_id}'))


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Legacy JSON contains a duplicate field')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Legacy JSON contains a non-finite number')


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or '\0' in value:
        raise ValueError(f'Legacy {label} must be nonempty text without NUL')
    return value


def _read_source(path):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source:
        source.execute('PRAGMA query_only=ON')
        source.execute('BEGIN')
        schema = source.execute("SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        if schema != [('meta','table'),('records','table')]:
            raise ValueError('Unrecognized legacy source schema')
        record_columns = [(row[1],row[2].upper(),row[3],row[5]) for row in source.execute('PRAGMA table_info(records)')]
        meta_columns = [(row[1],row[2].upper(),row[5]) for row in source.execute('PRAGMA table_info(meta)')]
        if record_columns != [('kind','TEXT',1,1),('id','TEXT',1,2),('body','TEXT',1,0)] or meta_columns != [('key','TEXT',1),('value','TEXT',0)]:
            raise ValueError('Unrecognized legacy source columns')
        raw_rows = source.execute('SELECT kind,id,body FROM records ORDER BY rowid').fetchall()
        meta = source.execute('SELECT key,value FROM meta ORDER BY key').fetchall()
    rows = []
    for position, (kind, record_id, raw) in enumerate(raw_rows):
        _text(kind, 'record kind')
        _text(record_id, 'record id')
        if not isinstance(raw, str):
            raise ValueError('Legacy body must be JSON text')
        try:
            body = json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_constant)
        except (ValueError, RecursionError) as exc:
            raise ValueError('Invalid legacy JSON body') from exc
        if not isinstance(body, dict) or body.get('id') != record_id:
            raise ValueError('Legacy body.id does not match its record id')
        rows.append(dict(kind=kind, id=record_id, source_body=raw, body=body, position=position))
    source_workspaces = [row for row in rows if row['kind'] == 'workspaces']
    source_users = [row for row in rows if row['kind'] == 'users']
    # This local-store format has one implicit workspace for comments, usage,
    # users and contribution history. Never guess ownership across workspaces.
    if len(source_workspaces) != 1 or not source_users:
        raise ValueError('Legacy import requires one workspace and at least one user')
    checksum = hashlib.sha256(json.dumps([raw_rows, meta], ensure_ascii=False, separators=(',',':')).encode()).hexdigest()
    source_id = _uuid('source', source_workspaces[0]['id'])
    return rows, source_workspaces[0], source_users, checksum, source_id


def _mapped_body(value, mapping):
    if isinstance(value, list):
        return [_mapped_body(item, mapping) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    actor_fields = {'assignee_id':'assignee_type', 'author_id':'author_type', 'creator_id':'creator_type', 'created_by_id':'created_by_type', 'lead_id':'lead_type', 'member_id':'member_type'}
    for key, item in value.items():
        if key == 'workspace_id' and isinstance(item, str):
            if item not in mapping['workspaces']:
                raise ValueError('Legacy record references an unknown workspace')
            result[key] = mapping['workspaces'][item]
        elif key in actor_fields and isinstance(item, str) and value.get(actor_fields[key]) in (None, 'member', 'user'):
            result[key] = mapping['users'].get(item, item)
        elif key in {'user_id', 'owner_id', 'created_by', 'updated_by', 'archived_by'} and isinstance(item, str):
            result[key] = mapping['users'].get(item, item)
        else:
            result[key] = _mapped_body(item, mapping)
    return result


def _plan(conn, rows, workspace_row, user_rows, checksum, source_id, source_path, owner_email):
    tables = set(conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").scalars())
    if not {'alembic_version','users','workspaces','members','issue_status'}.issubset(tables):
        raise ValueError('Target must be an existing migrated Python database')
    owner = conn.execute(select(users).where(users.c.email == owner_email.strip().lower())).mappings().one_or_none()
    if owner is None:
        raise ValueError('The requested owner email must already exist in the Python database')
    migration_required = not {'workspace_records', 'legacy_imports'}.issubset(tables)
    if not migration_required:
        existing = conn.execute(select(legacy_imports).where(or_(legacy_imports.c.source_id == source_id, legacy_imports.c.source_path == str(source_path)))).mappings().all()
        if existing:
            if len(existing) != 1 or existing[0]['source_checksum'] != checksum or existing[0]['source_id'] != source_id:
                raise ValueError('Legacy source changed since its completed import; explicit reconciliation is required')
            manifest = existing[0]
            if manifest['owner_id'] != owner['id']:
                raise ValueError('Legacy source was imported with a different owner')
            return dict(total_records=sum(manifest['counts'].values()), counts=manifest['counts'], mapping=manifest['mapping'], source_checksum=checksum, already_imported=True, migration_required=False), None
    raw_workspace = workspace_row['body']
    wid = _uuid('workspaces', workspace_row['id'])
    mapping = {'workspaces':{workspace_row['id']:wid}, 'users':{}, 'members':{}}
    user_values = []
    source_emails = set()
    for row in user_rows:
        body = row['body']
        email = _text(body.get('email'), 'user email').strip().lower()
        if email in source_emails:
            raise ValueError('Legacy users contain duplicate email identities')
        source_emails.add(email)
        name = _text(body.get('name'), 'user name')
        created_at = _text(body.get('created_at'), 'user created_at')
        uid = _uuid('users', row['id'])
        found = conn.execute(select(users).where(or_(users.c.id == uid, users.c.email == email))).mappings().all()
        if found:
            if len(found) == 1 and found[0]['id'] == owner['id'] and found[0]['email'] == email:
                uid = owner['id']
            else:
                raise ValueError('Legacy user conflicts with an existing Python identity')
        else:
            values = {column.name:body[column.name] for column in users.c if column.name in body}
            values.update(id=uid, email=email, name=name, created_at=created_at, updated_at=body.get('updated_at') or created_at)
            user_values.append(values)
        if uid in mapping['users'].values():
            raise ValueError('Legacy users contain duplicate identities')
        mapping['users'][row['id']] = uid
        mapping['members'][row['id']] = uid
    name = _text(raw_workspace.get('name'), 'workspace name')
    slug = _text(raw_workspace.get('slug'), 'workspace slug')
    if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise ValueError('Legacy workspace slug is invalid')
    if conn.execute(select(workspaces.c.id).where(or_(workspaces.c.id == wid, workspaces.c.slug == slug))).first():
        raise ValueError('Legacy workspace conflicts with an existing Python workspace')
    for uid in mapping['users'].values():
        if conn.execute(select(members.c.id).where(members.c.id == uid)).first():
            raise ValueError('Legacy member conflicts with an existing Python membership')
    created_at = _text(raw_workspace.get('created_at'), 'workspace created_at')
    prefix = raw_workspace.get('issue_prefix') or re.sub('[^A-Z0-9]', '', name.upper())[:10] or slug.replace('-','')[:4].upper()
    if not isinstance(prefix, str) or not re.fullmatch('[A-Z0-9]{1,10}', prefix):
        raise ValueError('Legacy workspace issue prefix is invalid')
    numbers = [row['body'].get('number', 0) for row in rows if row['kind'] == 'issues']
    counter = max([raw_workspace.get('issue_counter', 0)] + [n for n in numbers if isinstance(n, int) and not isinstance(n, bool)])
    workspace_values = {column.name:raw_workspace[column.name] for column in workspaces.c if column.name in raw_workspace}
    workspace_values.update(id=wid, name=name, slug=slug, issue_prefix=prefix, issue_counter=counter, created_at=created_at, updated_at=raw_workspace.get('updated_at') or created_at)
    imported = []
    for row in rows:
        body = _mapped_body(row['body'], mapping)
        if row['kind'] in {'workspaces', 'users'}:
            body['id'] = mapping[row['kind']][row['id']]
        if row['kind'] == 'preferences':
            if not body.get('user_id') and len(user_rows) == 1:
                body['user_id'] = next(iter(mapping['users'].values()))
            if body.get('user_id') not in mapping['users'].values():
                raise ValueError('Legacy preference ownership is ambiguous')
        imported.append(dict(row, workspace_id=wid, body=body))
    result = dict(total_records=len(rows), counts=dict(Counter(row['kind'] for row in rows)), mapping=mapping, source_checksum=checksum, already_imported=False, migration_required=migration_required)
    return result, dict(users=user_values, workspace=workspace_values, records=imported, owner_id=owner['id'], historical_role=raw_workspace.get('role','member') if len(user_rows)==1 else 'member')


def import_legacy(engine, source, owner_email, *, dry_run=False):
    """Return a nonsecret report; require an existing target and explicit owner.

    Dry-run uses a separate read-only connection, including on databases awaiting
    migration 0014. A real import requires migration to have run separately.
    """
    if engine.dialect.name != 'sqlite' or not engine.url.database or engine.url.database == ':memory:':
        raise ValueError('Legacy import requires a dedicated SQLite target file')
    source_path = Path(source).expanduser().absolute()
    target_path = Path(engine.url.database).resolve()
    if source_path.is_symlink():
        raise ValueError('Legacy source cannot be a symlink alias')
    source_path = source_path.resolve()
    if not source_path.is_file() or not target_path.is_file():
        raise ValueError('Source and target databases must already exist')
    if source_path == target_path or os.path.samefile(source_path, target_path):
        raise ValueError('Source and target cannot be aliases of the same database')
    try:
        rows, workspace_row, user_rows, checksum, source_id = _read_source(source_path)
    except sqlite3.DatabaseError as exc:
        raise ValueError('Unable to read a recognized legacy SQLite source') from exc
    target_engine = engine
    if dry_run:
        target_engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(target_path.as_uri() + '?mode=ro', uri=True))
    try:
        with target_engine.begin() as conn:
            # Writer serialization makes the manifest/conflict checks and all
            # inserted rows one atomic decision under concurrent invocations.
            conn.exec_driver_sql('BEGIN' if dry_run else 'BEGIN IMMEDIATE')
            if dry_run:
                conn.exec_driver_sql('PRAGMA query_only=ON')
            else:
                if not conn.exec_driver_sql('PRAGMA foreign_keys').scalar():
                    raise ValueError('Import requires target foreign key enforcement')
            result, plan = _plan(conn, rows, workspace_row, user_rows, checksum, source_id, source_path, owner_email)
            if dry_run or result['already_imported']:
                return dict(result, dry_run=dry_run)
            if result['migration_required']:
                raise ValueError('Run Python database migrations before importing legacy content')
            for values in plan['users']:
                conn.execute(users.insert().values(**values))
            conn.execute(workspaces.insert().values(**plan['workspace']))
            wid = plan['workspace']['id']
            created_at = plan['workspace']['created_at']
            for uid in result['mapping']['users'].values():
                role = 'owner' if uid == plan['owner_id'] else plan['historical_role']
                if role not in {'owner','admin','member'}:
                    raise ValueError('Legacy membership role is invalid')
                conn.execute(members.insert().values(id=uid, workspace_id=wid, user_id=uid, role=role, created_at=created_at))
            if plan['owner_id'] not in result['mapping']['users'].values():
                conn.execute(members.insert().values(id=_uuid('owner-members', wid + '/' + plan['owner_id']), workspace_id=wid, user_id=plan['owner_id'], role='owner', created_at=created_at))
            for position, (key, name, description, category, color) in enumerate(STATUSES):
                conn.execute(issue_status.insert().values(id=_uuid('issue-status', wid + '/' + key), workspace_id=wid, key=key, name=name, description=description, category=category, color=color, is_system=True, position=position, created_at=created_at, updated_at=created_at))
            conn.execute(records.insert(), plan['records'])
            conn.execute(legacy_imports.insert().values(source_id=source_id, source_path=str(source_path), source_checksum=checksum, workspace_id=wid, owner_id=plan['owner_id'], mapping=result['mapping'], counts=result['counts'], created_at=datetime.now(timezone.utc).isoformat()))
            return dict(result, dry_run=False)
    finally:
        if dry_run:
            target_engine.dispose()
