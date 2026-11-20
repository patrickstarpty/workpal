"""Thin Registry adapter for the workspace directory."""
from django import forms
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from .action_specs import obj, ROLES
from .directory import list_people, read_person


class DirectoryInput(forms.Form):
    query = forms.CharField(required=False, max_length=150, strip=False)
    cursor = forms.IntegerField(required=False, min_value=0, max_value=MAX_SQLITE_INTEGER)
    limit = forms.IntegerField(required=False, min_value=1, max_value=200)


def run(actor, payload, revision):
    data = list_people(actor, query=payload['query'],
                       cursor=0 if payload['cursor'] is None else payload['cursor'],
                       limit=50 if payload['limit'] is None else payload['limit'])
    return ActionResult('completed', [], data)


def register_actions():
    from workpal.actions.registry import register
    integer = dict(type='integer', minimum=0, maximum=MAX_SQLITE_INTEGER)
    person = obj(dict(user_id=dict(integer, minimum=1),
                      username=dict(type='string', maxLength=150)))
    output = obj(dict(person=person))
    output['required'] = []
    register(ActionSpec('workspace.people.read', PersonInput, output,
                        run_person, lambda actor, payload: (),
                        capability='read', allowed_roles=ROLES, mutating=False,
                        confirmation_required=False, revision_required=False,
                        audit_fields=('user_id',)))
    register(ActionSpec('workspace.people.list', DirectoryInput,
                        obj(dict(items=dict(type='array', items=person, maxItems=200),
                                 next_cursor=integer)), run, lambda actor, payload: (),
                        capability='read', allowed_roles=ROLES, mutating=False,
                        confirmation_required=False, revision_required=False,
                        audit_fields=('cursor', 'limit')))


class PersonInput(forms.Form):
    user_id = forms.IntegerField(min_value=1, max_value=MAX_SQLITE_INTEGER)


def run_person(actor, payload, revision):
    return ActionResult('completed', [], read_person(actor, payload['user_id']))
