"""Identity adapters for the shared action execution seam."""
from django import forms
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from .service import require_member, rename_workspace, manage_members

ROLES = ('owner', 'admin', 'member')
class Empty(forms.Form):
    pass
class Rename(forms.Form):
    name = forms.CharField(max_length=200)
class Create(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(max_length=4096, strip=False)
    role = forms.ChoiceField(choices=[(r, r) for r in ROLES])
class Revoke(forms.Form):
    membership_id = forms.IntegerField(min_value=1, max_value=MAX_SQLITE_INTEGER)
class SetRole(Revoke):
    role = forms.ChoiceField(choices=[(r, r) for r in ROLES])

def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)
INTEGER = {'type': 'integer'}
ROLE = {'type': 'string', 'enum': list(ROLES)}
WORKSPACE = obj(dict(id=INTEGER, name={'type': 'string'}, revision=INTEGER, role=ROLE))
MEMBER = obj(dict(id=INTEGER, username={'type': 'string'}, revision=INTEGER, role=ROLE))

def member_view(m):
    return dict(id=m.pk, username=m.user.username, role=m.role, revision=m.revision)

def handler(action):
    def run(actor, payload, revision):
        if action.startswith('workspace.'):
            m = require_member(actor, actor.workspace_id)
            w = (rename_workspace(actor, actor.workspace_id, payload['name'], revision)
                 if action == 'workspace.rename' else m.workspace)
            data = dict(id=w.pk, name=w.name, revision=w.revision, role=m.role)
        elif action == 'member.list':
            data = {'members': [member_view(m) for m in manage_members(actor, actor.workspace_id)]}
        elif action == 'member.create':
            data = member_view(manage_members(actor, actor.workspace_id, payload))
        else:
            m = manage_members(actor, actor.workspace_id,
                               dict(role=payload.get('role'), revision=revision),
                               payload['membership_id'], revoke=action == 'member.revoke')
            data = {} if m is None else member_view(m)
        return ActionResult('completed', [], data)
    return run

def register_actions():
    from workpal.actions.registry import register
    for action, form, schema, mutating, confirm, revision in (
        ('workspace.read', Empty, WORKSPACE, False, False, False),
        ('workspace.rename', Rename, WORKSPACE, True, False, True),
        ('member.list', Empty, obj({'members': {'type': 'array', 'items': MEMBER}}), False, False, False),
        ('member.create', Create, MEMBER, True, True, False),
        ('member.set_role', SetRole, MEMBER, True, True, True),
        ('member.revoke', Revoke, obj({}), True, True, True),
    ):
        register(ActionSpec(action, form, schema, handler(action), lambda actor, payload: (),
                            capability='write' if mutating else 'read',
                            allowed_roles=ROLES if action == 'workspace.read' else ROLES[:2],
                            mutating=mutating, confirmation_required=confirm,
                            audit_fields=tuple(k for k in form.base_fields if k != 'password'),
                            revision_required=revision))
