"""Caller owns commit/rollback. Invitations, deletion and runtime revocation pending."""
import re
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select, delete, update, func
from sqlalchemy.exc import IntegrityError
from .models import workspaces, members, issue_status
from .repository import membership
from workpal_backend.infrastructure.outbox import append_event

class WorkspaceValidationError(ValueError): pass
class WorkspaceConflictError(ValueError): pass
class WorkspaceAccessError(PermissionError): pass
class WorkspaceRoleError(WorkspaceAccessError): pass
class UnsupportedIdentityError(WorkspaceAccessError): pass
class WorkspaceNotFoundError(LookupError): pass

RESERVED = {'lg', 'ba', 'ak', 'or', 'changelog', 'ga', 'admin', 'na', 'rw', 'vi', 'fy', 'billing', 'licensing', 'views', 'cli', 'healthz', 'ht', 'tokens', 'pt-br', 'an', 'kg', 'kl', 'az', 'ru', 'eu', 'mr', 'onboarding', 'solutions', 'ln', 'workpal', 'invite', 'mi', 'so', 'search', 'en', 'product', 'ms', 'es', 'my', 'fi', 'ro', 'security', 'www', 'health', 'sdk', 'af', 'password', 'ja', 'callback', 'pl', 'yo', 'zh-hant', 'ks', 'abuse', 'kj', 'hr', 'manifest.json', 'ng', 'ug', 'li', 'bg', 'wo', 'dingtalk', 'tg', 'wa', 'my-issues', 'pt', 'ti', 'account', 'nn', 'oc', 'ce', 'metrics', 'lv', 'xh', 'fr', 'io', 'hi', 'ch', 'nb', 'nv', 'sc', 'members', '_next', 'terms', 'lu', 'cu', 'robots.txt', 'sk', 'as', 'os', 'ps', 'bi', 'signout', 'br', 'qu', 'fj', 'mk', 'blog', 'bs', 'gv', 'hy', 'sv', 'tk', 'rn', 've', '.well-known', 'auth', 'lb', 'ha', 'docs', 'jv', 'kn', 'webhooks', 'bm', 'inbox', 'sm', 'eo', 'es-mx', 'projects', 'v1', 'ay', 'it', 'privacy', 'mh', 'pt-pt', 'sl', 'settings', 'public', 'help', 'gd', 'uk', 'en-gb', 'v2', 'ae', 'ab', 'sn', 'pi', 'dashboard', 'en-us', 'ka', 'noreply', 'verify', 'be', 'mg', 'press', 'sq', 'id', 'zh-hans', 'ws', 'ss', 'is', 'ig', 'et', 'sd', 'st', 'kv', 'signin', 'pa', 'profile', 'api', 'he', 'nl', 'oj', 'tl', 'cy', 'th', 'cdn', 'gn', 'ho', 'runtimes', 'hz', 'graphql', 'favicon.ico', 'sitemap.xml', 'tn', 'cv', 'hostmaster', 'rm', 'cs', 'ky', 'autopilots', 'sw', 'usage', 'am', 'status', 'oauth', 'issues', 'ii', 'kr', 'es-419', 'lark', 'aa', 'hu', 'om', 'vo', 'workspaces', 'la', 'customers', 'contact-sales', 'ia', 'kk', 'ping', 'mn', 'zu', 'reset', 'to', 'cr', 'invitations', 'squads', 'uz', 'lt', 'agents', 'notifications', 'logout', 'usecases', 'kw', 'teams', 'tt', 'dv', 'no', 'wecom', 'bo', 'homepage', 'ff', 'se', 'ty', 'mail', 'zh-hk', 'ie', 'uploads', 'ki', 'gu', 'webmaster', 'ku', 'te', 'tr', 'ca', 'ml', 'ta', 'zh-cn', 'nd', 'su', 'assets', 'pricing', 'fo', 'km', 'skills', 'static', 'fa', 'sg', 'careers', 'download', 'gl', 'legal', 'fr-ca', 'ftp', 'nr', 'readyz', 'signup', 'de', 'lo', 'yi', 'ne', 'ko', 'ts', 'slack', 'da', 'about', 'mt', 'ny', 'el', 'sa', 'ar', 'dz', 'iu', 'new', 'telegram', 'ik', 'si', 'tw', 'co', 'home', 'bn', 'login', 'zh', 'contact', 'postmaster', 'av', 'ee', 'sr', 'za', 'zh-tw', 'support', 'files', 'ur'}
STATUSES = [('backlog', 'Backlog', 'Parked. Assigning an issue here never starts an agent run.', 'unstarted', '#6b7280'), ('todo', 'Todo', 'Queued for work. Moving an issue here starts the assigned agent.', 'unstarted', '#6b7280'), ('in_progress', 'In Progress', 'Actively being worked on.', 'started', '#f59e0b'), ('in_review', 'In Review', 'Work delivered, waiting on human review. Finalizes the autopilot run.', 'started', '#22c55e'), ('done', 'Done', 'Completed.', 'done', '#3b82f6'), ('blocked', 'Blocked', 'Stalled on an external dependency.', 'started', '#ef4444'), ('cancelled', 'Cancelled', 'Decided not to do.', 'closed', '#6b7280')]

def response(row):
    return {k: row[k] for k in ('id','name','slug','description','context','settings','repos','issue_prefix','avatar_url','created_at','updated_at')}

def create_workspace(session, user_id, name, slug, issue_prefix=None):
    if not isinstance(name, str) or not isinstance(slug, str):
        raise WorkspaceValidationError('name and slug are required')
    name, slug = name.strip(), slug.strip().lower()
    if not name or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug in RESERVED:
        raise WorkspaceValidationError('invalid or reserved slug, or empty name')
    if issue_prefix is not None and not isinstance(issue_prefix, str):
        raise WorkspaceValidationError('invalid issue prefix')
    prefix = (issue_prefix or '').strip().upper()
    if prefix and not re.fullmatch('[A-Z0-9]{1,10}', prefix):
        raise WorkspaceValidationError('invalid issue prefix')
    prefix = prefix or slug.replace('-', '')[:4].upper()
    now = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    wid = str(uuid4())
    # Ensure a real outer SQLite transaction before SAVEPOINT (legacy sqlite driver).
    conn = session.connection()
    if not conn.connection.driver_connection.in_transaction:
        conn.exec_driver_sql('BEGIN')
    try:
        with session.begin_nested():
            session.execute(workspaces.insert().values(id=wid,name=name,slug=slug,issue_prefix=prefix,created_at=now,updated_at=now))
            session.execute(members.insert().values(id=str(uuid4()),workspace_id=wid,user_id=user_id,role='owner',created_at=now))
            for key, label, description, category, color in STATUSES:
                session.execute(issue_status.insert().values(id=str(uuid4()),workspace_id=wid,key=key,name=label,description=description,category=category,color=color,is_system=True,position=0,created_at=now,updated_at=now))
            return response(session.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one())
    except IntegrityError as exc:
        if 'workspaces.slug' in str(exc):
            raise WorkspaceConflictError('workspace slug already exists') from exc
        raise

def list_workspaces(session, user_id):
    rows = session.execute(select(workspaces, members.c.pinned_at).join(members).where(members.c.user_id == user_id).order_by(members.c.pinned_at.desc().nulls_last(),workspaces.c.created_at,workspaces.c.id)).mappings()
    return [dict(response(r), **({'pinned_at':r['pinned_at']} if r['pinned_at'] else {})) for r in rows]

def require_workspace_access(session, principal, workspace_id):
    def field(k):
        return principal.get(k) if isinstance(principal, dict) else getattr(principal,k,None)
    if field('identity_kind') != 'session':
        raise UnsupportedIdentityError('only session identities are supported')
    member = membership(session, field('user_id'), workspace_id)
    if member is None:
        raise WorkspaceAccessError('workspace access denied')
    return dict(member)

def get_workspace(session, principal, workspace_id):
    require_workspace_access(session, principal, workspace_id)
    return response(session.execute(select(workspaces).where(workspaces.c.id == workspace_id)).mappings().one())

def remove_membership(session, principal, workspace_id, member_id):
    # Acquire SQLite writer serialization BEFORE reading membership/owner count.
    # UPDATE also works inside an already active caller transaction; never commits it.
    session.execute(update(workspaces).where(workspaces.c.id == workspace_id).values(issue_counter=workspaces.c.issue_counter))
    actor = require_workspace_access(session, principal, workspace_id)
    target = session.execute(select(members).where(members.c.id == member_id, members.c.workspace_id == workspace_id)).mappings().one_or_none()
    if target is None:
        raise WorkspaceNotFoundError('member not found')
    if actor['id'] != member_id and actor['role'] not in ('owner','admin'):
        raise WorkspaceAccessError('workspace admin required')
    if target['role'] == 'owner':
        if actor['role'] != 'owner':
            raise WorkspaceAccessError('workspace owner required')
        count = session.scalar(select(func.count()).select_from(members).where(members.c.workspace_id == workspace_id,members.c.role == 'owner'))
        if count <= 1:
            raise WorkspaceValidationError('workspace must have at least one owner')
    session.execute(delete(members).where(members.c.id == member_id))


def update_workspace(session, principal, workspace_id, body):
    actor = require_workspace_access(session, principal, workspace_id)
    if actor['role'] not in ('owner', 'admin'):
        raise WorkspaceRoleError('insufficient permissions')
    stored = get_workspace(session, principal, workspace_id)
    values = {k:v for k,v in body.items() if v is not None}
    if 'name' in values:
        values['name'] = values['name'].strip()
        if not values['name']:
            raise WorkspaceValidationError('name is required')
    if 'issue_prefix' in values:
        prefix = values.pop('issue_prefix').strip().upper()
        if prefix and not re.fullmatch('[A-Z0-9]{1,10}', prefix):
            raise WorkspaceValidationError('issue prefix must be 1-10 uppercase letters or digits')
        if prefix:
            values['issue_prefix'] = prefix
    if 'avatar_url' in values:
        values['avatar_url'] = values['avatar_url'].strip()
    if 'repos' in values:
        from urllib.parse import urlsplit
        repos, seen = [], set()
        if not isinstance(values['repos'], list):
            raise WorkspaceValidationError('repos must be an array of repository objects')
        for i, item in enumerate(values['repos']):
            if not isinstance(item, dict) or any(item.get(k) is not None and not isinstance(item[k], str) for k in ('url','description')):
                raise WorkspaceValidationError('repos must be an array of repository objects')
            url = (item.get('url') or '').strip()
            description = (item.get('description') or '').strip()
            if not url:
                raise WorkspaceValidationError(f'repos[{i}]: url is required')
            try:
                parsed = urlsplit(url)
                valid = bool(parsed.netloc and parsed.scheme in ('http','https','ssh','git'))
            except ValueError:
                valid = False
            colon, at = url.find(':'), url.find('@')
            valid = valid or (' ' not in url and '://' not in url and 0 < colon < len(url)-1 and at < colon and bool(url[at+1:colon]))
            if not valid:
                raise WorkspaceValidationError(f'repos[{i}]: url must be a valid http(s) or ssh git URL')
            if url not in seen:
                repos.append(dict(url=url, **({'description':description} if description else {})))
                seen.add(url)
        values['repos'] = repos
    incoming = values.get('settings')
    if isinstance(incoming, dict):
        incoming = incoming.copy()
        key = 'pr_auto_complete_enabled'
        def legacy(s):
            return s.get(key) is None or s.get(key) is True
        old = stored['settings'] if isinstance(stored['settings'], dict) else {}
        if key in incoming and legacy(incoming) != legacy(old):
            incoming['pr_merge_status'] = 'done' if legacy(incoming) else 'none'
        raw = incoming.get('pr_merge_status')
        target = ('done' if legacy(incoming) else 'none') if raw is None else (raw.strip().lower() or 'none' if isinstance(raw,str) else 'none')
        if target == 'none':
            incoming[key] = False
        else:
            incoming.pop(key, None)
        values['settings'] = incoming
    values['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
    session.execute(update(workspaces).where(workspaces.c.id == workspace_id).values(**values))
    result = get_workspace(session, principal, workspace_id)
    append_event(session, dict(type="workspace:updated", workspaceID=workspace_id,
        actorType="member", actorID=actor["user_id"], payload={"workspace": result}))
    return result


def set_pinned(session, principal, workspace_id, pinned):
    actor = require_workspace_access(session, principal, workspace_id)
    if type(pinned) is not bool:
        raise WorkspaceValidationError('pinned must be a boolean')
    timestamp = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z') if pinned else None
    session.execute(update(members).where(members.c.id == actor['id']).values(pinned_at=timestamp))
    return {'pinned_at':timestamp}


def list_members(session, principal, workspace_id):
    from workpal_backend.auth.models import users
    require_workspace_access(session, principal, workspace_id)
    columns = [members.c[k] for k in ('id','workspace_id','user_id','role','created_at')]
    columns += [users.c[k] for k in ('name','email','avatar_url')]
    return [dict(r) for r in session.execute(select(*columns).join(users, users.c.id == members.c.user_id).where(members.c.workspace_id == workspace_id).order_by(members.c.created_at)).mappings()]
