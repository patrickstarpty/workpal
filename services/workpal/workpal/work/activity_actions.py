"""Thin Registry adapter for audit-owned activity."""
from django import forms
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult
from workpal.audit.activity import list_issue_activity
from .issue_actions import Select, STR, INT, resolve
from .actions import obj

class Page(Select):
    cursor = forms.CharField(required=False, max_length=2048, strip=False)
    limit = forms.IntegerField(required=False, min_value=1, max_value=200)
    def clean(self):
        data = super().clean()
        data['cursor'] = data.get('cursor') or ''
        data['limit'] = data.get('limit') or 50
        return data

def run(actor, payload, revision):
    page, refs = list_issue_activity(actor, **payload)
    return ActionResult('completed', refs, page)

def register_actions():
    from workpal.actions.registry import register
    item = obj(dict(id=STR, action_id=STR, actor_user_id=INT, created_at=STR,
                    object_refs={'type':'array','items':obj(dict(kind=STR,id=STR))}))
    register(ActionSpec('issue.activity.list', Page,
        obj(dict(items={'type':'array','items':item}, next_cursor=STR)), run, resolve,
        capability='read', mutating=False))
