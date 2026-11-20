"""Current hierarchy with append-only provenance and transactional CAS."""
from django.utils import timezone
from workpal.contracts import DomainError
from workpal.access.service import register_object
from workpal.storage import atomic_write
from . import issues
from .models import Issue

def parent_for_write(actor,parent_issue_id):
    issues.integer(parent_issue_id,True)
    if not parent_issue_id: return None
    parent=issues.selected(actor,parent_issue_id,'write')
    if parent.archived: raise DomainError('issue_archived','Parent archived.',status=409)
    return parent

def set_parent(actor,issue_id,parent_issue_id,revision):
    def write():
        issues.integer(revision)
        row=issues.selected(actor,issue_id,'write')
        parent=parent_for_write(actor,parent_issue_id)
        seen={row.pk}; current=parent
        while current:
            if current.pk in seen: raise DomainError('hierarchy_cycle','Hierarchy cycle.',status=409)
            seen.add(current.pk)
            current=Issue.objects.filter(pk=current.parent_id).first() if current.parent_id else None
        if not Issue.objects.filter(pk=row.pk,revision=revision).update(parent=parent,revision=revision+1,updated_at=timezone.now()):
            raise DomainError('revision_conflict','Issue changed.',status=409)
        if parent: register_object(actor.workspace_id,issues.ref(row.pk),[issues.ref(parent.pk)])
        issues.assignee(actor,row,row.assignee_id or 0)
        row.refresh_from_db()
        return issues.view(row, actor)
    return atomic_write(write)

def children(actor,issue_id,**filters):
    issues.selected(actor,issue_id)
    return issues.list_issues(actor,parent_issue_id=issue_id,**filters)
