"""Current provenance and recipient isolation behind a small transactional interface."""
from django.utils import timezone
from workpal.contracts import Actor, ObjectRef, DomainError
from workpal.identity.service import require_member
from workpal.access.service import authorize, register_object
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from workpal.work import issues
from workpal.work.resources import sources
from .models import Comment, Subscription, Notification

def fail(): raise DomainError('invalid_input','Invalid collaboration fields.')
def integer(value, zero=False):
    if type(value) is not int or not (0 if zero else 1) <= value < MAX_SQLITE_INTEGER: fail()
def ref(pk, notification=False): return ObjectRef('notification' if notification else 'comment',str(pk))
def comment_view(row):
    return dict(id=row.pk,issue_id=row.issue_id,author_user_id=row.author_id,body=row.body,
                archived=row.archived,updated_at=row.updated_at.isoformat(),mentions=list(row.mention_user_ids),revision=row.revision,created_at=row.created_at.isoformat())
def selected(actor, pk, notification=False):
    integer(pk)
    require_member(actor,actor.workspace_id)
    model=Notification if notification else Comment
    query=dict(pk=pk,workspace_id=actor.workspace_id)
    if notification: query['recipient_id']=actor.user_id
    row=model.objects.filter(**query).first()
    if row is None: raise DomainError('not_found','Record unavailable.',status=404)
    issues.read(actor,row.issue_id)
    authorize(actor,'read',[ref(pk,notification)])
    return row

def _source_refs(values):
    refs=sources(values)
    for source in refs:
        for value in (source.kind,source.id):
            try: value.encode('utf8')
            except UnicodeError: fail()
    return refs

def create_refs(actor,issue_id,source_refs=None):
    issues.read(actor,issue_id)
    refs=[issues.ref(issue_id)]+_source_refs([] if source_refs is None else source_refs)
    authorize(actor,'write',refs)
    return refs

def _notify_comment(actor,row):
    """Trusted internal hook: called inside the comment's atomic_write only.

    Event identity is derived from the persisted comment; no caller-controlled
    event keys, grants, external dispatch or future assignment kinds.
    """
    explicit=set(row.mention_user_ids)
    candidates=explicit | set(Subscription.objects.filter(workspace_id=actor.workspace_id,
        issue_id=row.issue_id,active=True).values_list('user_id',flat=True))
    for user_id in sorted(candidates):
        recipient=Actor(user_id,actor.workspace_id)
        try:
            require_member(recipient,actor.workspace_id)
            authorize(recipient,'read',[ref(row.pk)])
            issues.read(recipient,row.issue_id)
        except DomainError as error:
            if user_id in explicit or error.status not in (403,404): raise
            continue
        if user_id==actor.user_id: continue
        notification,_=Notification.objects.get_or_create(workspace_id=actor.workspace_id,
            recipient_id=user_id,event_key=f'comment:{row.pk}',defaults=dict(issue_id=row.issue_id,
            comment=row,kind='mention' if user_id in explicit else 'comment'))
        register_object(actor.workspace_id,ref(notification.pk,True),[issues.ref(row.issue_id),ref(row.pk)])

def notify_comment(actor,row):
    """Trusted transactional hook for a persisted comment, with dynamic recipients."""
    def write():
        current=selected(actor,row.pk)
        authorize(actor,'write',[ref(current.pk)])
        return _notify_comment(actor,current)
    return atomic_write(write)

def create(actor,issue_id,body,mention_user_ids=None,source_refs=None):
    def write():
        integer(issue_id)
        issues.validate_text(body,20000,True)
        mentions=[] if mention_user_ids is None else mention_user_ids
        if type(mentions) is not list or len(mentions)>50: fail()
        for user_id in mentions: integer(user_id)
        if len(set(mentions))!=len(mentions): fail()
        refs=create_refs(actor,issue_id,source_refs)
        if issues.read(actor,issue_id)['archived']:
            raise DomainError('issue_archived','Issue archived.',status=409)
        row=Comment.objects.create(workspace_id=actor.workspace_id,issue_id=issue_id,
            author_id=actor.user_id,body=body,mention_user_ids=list(mentions))
        register_object(actor.workspace_id,ref(row.pk),refs)
        notify_comment(actor,row)
        return comment_view(row)
    return atomic_write(write)

def read(actor,comment_id): return comment_view(selected(actor,comment_id))
def subscription(actor,issue_id,active=None):
    def operation():
        integer(issue_id)
        issues.read(actor,issue_id)
        if active is not None and type(active) is not bool: fail()
        if active is not None:
            Subscription.objects.update_or_create(workspace_id=actor.workspace_id,issue_id=issue_id,
                user_id=actor.user_id,defaults=dict(active=active))
        subscribed=Subscription.objects.filter(workspace_id=actor.workspace_id,issue_id=issue_id,
            user_id=actor.user_id,active=True).exists()
        return dict(issue_id=issue_id,subscribed=subscribed)
    return operation() if active is None else atomic_write(operation)

def notification_view(actor,row):
    # Caller has authorized all notification sources before title projection.
    title=issues.read(actor,row.issue_id)['title']
    return dict(id=row.pk,issue_id=row.issue_id,comment_id=row.comment_id or 0,kind=row.kind,
        issue_title=title,revision=row.revision,read_at=row.read_at.isoformat() if row.read_at else '',
        created_at=row.created_at.isoformat())
def mark_read(actor,notification_id,revision):
    return _mark(actor,notification_id,revision,True)

def mark_unread(actor,notification_id,revision):
    return _mark(actor,notification_id,revision,False)

def _mark(actor,notification_id,revision,read):
    def write():
        integer(revision)
        row=selected(actor,notification_id,True)
        if not Notification.objects.filter(pk=row.pk,revision=revision).update(read_at=timezone.now() if read else None,revision=revision+1):
            raise DomainError('revision_conflict','Notification changed.',status=409)
        row.refresh_from_db()
        return notification_view(actor,row)
    return atomic_write(write)

def listing(actor,issue_id=None,unread_only=False,cursor=0,limit=50,include_archived=False):
    require_member(actor,actor.workspace_id)
    integer(cursor,True); integer(limit)
    if limit>200 or type(unread_only) is not bool or type(include_archived) is not bool: fail()
    notification=issue_id is None
    model=Notification if notification else Comment
    query=dict(workspace_id=actor.workspace_id,pk__gt=cursor)
    if notification:
        query['recipient_id']=actor.user_id
        if unread_only: query['read_at__isnull']=True
    else:
        issues.read(actor,issue_id)
        query['issue_id']=issue_id
        if not include_archived: query['archived']=False
    visible=[]
    for row in model.objects.filter(**query).order_by('pk').iterator():
        try: selected(actor,row.pk,notification)
        except DomainError as error:
            if error.status not in (403,404): raise
            continue
        visible.append(notification_view(actor,row) if notification else comment_view(row))
        if len(visible)>limit: break
    return dict(items=visible[:limit],next_cursor=visible[limit-1]['id'] if len(visible)>limit else 0)


def management_refs(actor,comment_id,**changes):
    row=selected(actor,comment_id)
    member=require_member(actor,actor.workspace_id)
    if row.author_id!=actor.user_id and member.role not in ('owner','admin'):
        raise DomainError('permission_denied','Permission denied.',status=403)
    refs=[issues.ref(row.issue_id),ref(row.pk)]+_source_refs(changes.get('source_refs',[]))
    authorize(actor,'write',refs)
    return refs

def manage(actor,comment_id,revision,operation,**changes):
    def write():
        if operation not in ('update','remove','restore') or set(changes)-{'body','mention_user_ids','source_refs'}: fail()
        if operation!='update' and changes: fail()
        management_refs(actor,comment_id,**changes)
        row=selected(actor,comment_id)
        integer(revision)
        values=dict(revision=revision+1,updated_at=timezone.now())
        added=set()
        if operation=='update':
            if row.archived: raise DomainError('comment_archived','Restore comment first.',status=409)
            if not changes: fail()
            if 'body' in changes:
                issues.validate_text(changes['body'],20000,True)
                values['body']=changes['body']
            if 'mention_user_ids' in changes:
                mentions=changes['mention_user_ids']
                if type(mentions) is not list or len(mentions)>50: fail()
                for uid in mentions: integer(uid)
                if len(set(mentions))!=len(mentions): fail()
                added=set(mentions)-set(row.mention_user_ids)
                values['mention_user_ids']=mentions
        else: values['archived']=operation=='remove'
        if not Comment.objects.filter(pk=row.pk,revision=revision).update(**values):
            raise DomainError('revision_conflict','Comment changed.',status=409)
        if changes.get('source_refs'): register_object(actor.workspace_id,ref(row.pk),_source_refs(changes['source_refs']))
        row.refresh_from_db()
        for uid in sorted(added):
            recipient=Actor(uid,actor.workspace_id)
            selected(recipient,row.pk)
            if uid==actor.user_id: continue
            notification,_=Notification.objects.get_or_create(workspace_id=actor.workspace_id,recipient_id=uid,
                event_key=f'comment:{row.pk}:revision:{row.revision}',defaults=dict(issue_id=row.issue_id,comment=row,kind='mention'))
            register_object(actor.workspace_id,ref(notification.pk,True),[issues.ref(row.issue_id),ref(row.pk)])
        return comment_view(row)
    return atomic_write(write)


def _notify_issue(actor, issue_id, revision, kind):
    def write():
        integer(issue_id); integer(revision)
        current = issues.read(actor, issue_id)
        authorize(actor, 'write', [issues.ref(issue_id)])
        if current['revision'] != revision:
            raise DomainError('revision_conflict', 'Issue changed.', status=409)
        if kind == 'blocked' and current['status_category'] != 'blocked':
            raise DomainError('invalid_transition', 'Issue is not blocked.', status=409)
        recipient_id = current['assignee_user_id' if kind == 'assignment' else 'blocked_owner_user_id']
        if not recipient_id:
            return
        recipient = Actor(recipient_id, actor.workspace_id)
        require_member(recipient, actor.workspace_id)
        issues.read(recipient, issue_id)
        if kind == 'assignment' and recipient_id == actor.user_id and actor.executor_id is None:
            return
        notification, _ = Notification.objects.get_or_create(
            workspace_id=actor.workspace_id, recipient_id=recipient_id,
            event_key=f'issue:{issue_id}:{kind}:{revision}',
            defaults=dict(issue_id=issue_id, kind=kind))
        register_object(actor.workspace_id, ref(notification.pk, True), [issues.ref(issue_id)])
    return atomic_write(write)


def notify_assignment(actor, issue_id, revision):
    """Notify the persisted assignee; event identity and recipients are internal."""
    return _notify_issue(actor, issue_id, revision, 'assignment')


def notify_blocked(actor, issue_id, revision):
    """Notify the persisted blocked decision owner, including the acting human."""
    return _notify_issue(actor, issue_id, revision, 'blocked')
