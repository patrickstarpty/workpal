"""Bounded active dependencies and append-only provenance."""
from django.utils import timezone
from workpal.contracts import DomainError
from workpal.access.service import register_object
from workpal.storage import atomic_write
from . import issues
from .models import Issue, IssueDependency
from .transitions import category

def unresolved_dependencies(actor,issue_id):
    row=issues.selected(actor,issue_id)
    return any(category(edge.depends_on)!='done' for edge in IssueDependency.objects.filter(issue=row,active=True).select_related('depends_on'))

def change(actor,issue_id,depends_on_id,revision,active):
    def write():
        issues.integer(revision)
        a=issues.selected(actor,issue_id,'write'); b=issues.selected(actor,depends_on_id,'write')
        if a.revision!=revision: raise DomainError('revision_conflict','Issue changed.',status=409)
        if a.pk==b.pk: raise DomainError('dependency_cycle','Dependency unavailable.',status=409)
        edge=IssueDependency.objects.filter(issue=a,depends_on=b).first()
        if active:
            if edge and edge.active: raise DomainError('dependency_exists','Dependency exists.',status=409)
            if IssueDependency.objects.filter(issue=a,active=True).count()>=100: issues.fail()
            seen=set(); pending=[b.pk]
            while pending:
                current=pending.pop()
                if current==a.pk: raise DomainError('dependency_cycle','Dependency unavailable.',status=409)
                if current in seen: continue
                seen.add(current)
                pending.extend(IssueDependency.objects.filter(issue_id=current,active=True).values_list('depends_on_id',flat=True))
            register_object(actor.workspace_id,issues.ref(a.pk),[issues.ref(b.pk)])
            if edge: edge.active=True; edge.save(update_fields=['active'])
            else: IssueDependency.objects.create(issue=a,depends_on=b)
        else:
            if not edge or not edge.active: raise DomainError('not_found','Dependency unavailable.',status=404)
            edge.active=False; edge.save(update_fields=['active'])
        if not Issue.objects.filter(pk=a.pk,revision=revision).update(revision=revision+1,updated_at=timezone.now()):
            raise DomainError('revision_conflict','Issue changed.',status=409)
        a.refresh_from_db(); return issues.view(a, actor)
    return atomic_write(write)

def add(actor,issue_id,depends_on_id,revision): return change(actor,issue_id,depends_on_id,revision,True)
def remove(actor,issue_id,depends_on_id,revision): return change(actor,issue_id,depends_on_id,revision,False)
def list_dependencies(actor,issue_id,cursor=0,limit=50):
    a=issues.selected(actor,issue_id); issues.integer(cursor,True); issues.integer(limit)
    if limit>200: issues.fail()
    items=[]
    for edge in IssueDependency.objects.filter(issue=a,active=True,pk__gt=cursor).select_related('depends_on').order_by('pk'):
        try: b=issues.selected(actor,edge.depends_on_id)
        except DomainError as e:
            if e.status not in (403,404): raise
            continue
        items.append(dict(id=edge.pk,depends_on_id=b.pk,status_key=b.status_key,status_category=category(b)))
        if len(items)>limit: break
    return dict(items=items[:limit],next_cursor=items[limit-1]['id'] if len(items)>limit else 0)
