"""Issue-local workflow facts; completion has no execution side effects."""
from copy import deepcopy
from django.utils import timezone
from workpal.contracts import DomainError, ObjectRef, SubjectRef
from workpal.identity.service import require_member
from workpal.access.service import authorize, register_object, derive_scope
from workpal.storage import atomic_write
from . import issues
from .models import Issue, IssueTransition

def category(row):
    return next(s['category'] for s in row.workflow_snapshot['definition']['states'] if s['key']==row.status_key)

def ref(history_id):
    return ObjectRef('issue_transition', str(history_id))

def authorize_target(actor, row, target):
    """Current decision authority also applies to a cached completion result."""
    definition = row.workflow_snapshot['definition']
    if any(state['key'] == target and state['category'] == 'done' for state in definition['states']):
        member = require_member(actor, actor.workspace_id)
        if actor.executor_id is not None or member.role not in definition['review_policy']['reviewer_roles']:
            raise DomainError('permission_denied', 'Human reviewer required.', status=403)

def transition(actor,issue_id,target,revision,reason='',blocked_owner_user_id=0):
    def write():
        issues.integer(revision); issues.integer(blocked_owner_user_id,True)
        issues.validate_text(target,64,True); issues.validate_text(reason,4000)
        row=issues.selected(actor,issue_id,'write')
        if row.revision!=revision: raise DomainError('revision_conflict','Issue changed.',status=409)
        definition=row.workflow_snapshot['definition']
        states={s['key']:s['category'] for s in definition['states']}
        if target not in states or {'from':row.status_key,'to':target} not in definition['transitions']:
            raise DomainError('invalid_transition','Transition unavailable.',status=409)
        cat=states[target]
        if cat=='blocked':
            if not reason.strip() or not blocked_owner_user_id: issues.fail()
            issues.assignee(actor,row,blocked_owner_user_id)
        elif blocked_owner_user_id: issues.fail()
        snapshot = {}
        completion_refs = []
        if cat=='done':
            authorize_target(actor,row,target)
            if not reason.strip(): issues.fail()
            policy = definition['review_policy']['completion']
            if policy == 'approved_delivery':
                from workpal.delivery import approval
                snapshot, completion_refs = approval.inspect(actor, SubjectRef('issue', str(issue_id)))
                if snapshot['status'] != 'approved':
                    raise DomainError('completion_not_ready','Completion evidence unavailable.',status=409)
                authorize(actor, 'write', completion_refs)
                register_object(actor.workspace_id, issues.ref(row.pk), derive_scope(completion_refs).source_refs)
                issues.assignee(actor, row, row.assignee_id)
            elif policy != 'manual':
                raise DomainError('completion_not_ready','Completion evidence unavailable.',status=409)
            from .dependencies import unresolved_dependencies
            if unresolved_dependencies(actor,issue_id):
                raise DomainError('dependency_blocked','Dependencies incomplete.',status=409)
        owner=blocked_owner_user_id if cat=='blocked' else 0
        blocked=reason if cat=='blocked' else ''
        if not Issue.objects.filter(pk=row.pk,revision=revision).update(status_key=target,blocked_owner_id=owner or None,blocked_reason=blocked,revision=revision+1,updated_at=timezone.now()):
            raise DomainError('revision_conflict','Issue changed.',status=409)
        history=IssueTransition.objects.create(completion_review_id=snapshot.get("review_id"),completion_snapshot=deepcopy(snapshot),issue=row,from_key=row.status_key,to_key=target,actor_user_id=actor.user_id,actor_executor_id=actor.executor_id,reason=reason,before_blocked_owner_id=row.blocked_owner_id or 0,after_blocked_owner_id=owner,before_blocked_reason=row.blocked_reason,after_blocked_reason=blocked,requirements_version_id=row.current_requirements_id,workflow_sha256=row.workflow_snapshot['sha256'],revision=revision+1)
        register_object(actor.workspace_id,ref(history.pk),[issues.ref(row.pk)]+completion_refs)
        row.refresh_from_db()
        if cat == 'blocked':
            from workpal.collaboration.service import notify_blocked
            notify_blocked(actor,row.pk,row.revision)
        return issues.view(row, actor)
    return atomic_write(write)

def list_transitions(actor,issue_id,cursor=0,limit=50):
    row=issues.selected(actor,issue_id)
    issues.integer(cursor,True); issues.integer(limit)
    if limit>200: issues.fail()
    rows=[]
    for history in IssueTransition.objects.filter(issue=row,pk__gt=cursor).order_by('pk').iterator():
        try:
            authorize(actor,'read',[ref(history.pk)])
        except DomainError as error:
            if error.status != 403: raise
            continue
        rows.append(history)
        if len(rows)>limit: break
    fields=('id','issue_id','from_key','to_key','actor_user_id','actor_executor_id','reason','before_blocked_owner_id','after_blocked_owner_id','before_blocked_reason','after_blocked_reason','requirements_version_id','workflow_sha256','revision')
    return dict(items=[dict(**{k:(getattr(r,k) or '' if k=='actor_executor_id' else getattr(r,k)) for k in fields},created_at=r.created_at.isoformat(),**({"approval":deepcopy(r.completion_snapshot)} if r.completion_snapshot else {})) for r in rows[:limit]],next_cursor=rows[limit-1].pk if len(rows)>limit else 0)
