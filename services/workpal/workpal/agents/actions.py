from django import forms
from workpal.actions.contracts import ActionSpec
from workpal.actions.registry import register
from workpal.contracts import ActionResult
from workpal.work.actions import obj
from . import service
S={'type':'string'}; I={'type':'integer'}
VIEW=obj({**{k:S for k in ('name','provider_key','model','created_at','capability')},**{k:I for k in ('id','workspace_id','revision','created_by')}})
class Create(forms.Form):
    name=forms.CharField(max_length=200,strip=False)
    provider_key=forms.ChoiceField(choices=[(p,p) for p in service.PROVIDERS],required=False)
    model=forms.CharField(max_length=200,required=False,strip=False)
class Select(forms.Form):
    agent_id=forms.IntegerField(min_value=1)
class Update(Select):
    name=forms.CharField(max_length=200,strip=False,required=False)
    provider_key=forms.ChoiceField(choices=[(p,p) for p in service.PROVIDERS],required=False)
    model=forms.CharField(max_length=200,required=False,strip=False)
    def clean(self):
        values=super().clean()
        return {k:v for k,v in values.items() if k in self.data}


def register_actions():
    for action,form in [('create',Create),('read',Select),('update',Update)]:
        def handler(actor,payload,revision,action=action):
            p=dict(payload)
            if action=='read': data=service.read(actor,**p)
            else:
                if action=='create': p['provider_key']=p['provider_key'] or 'copilot_cli'
                data=service.create(actor,**p) if action=='create' else service.update(actor,revision=revision,**p)
            return ActionResult('completed',[service.ref(data['id'])],data)
        register(ActionSpec('agent.'+action,form,VIEW,handler,lambda a,p:[service.ref(p['agent_id'])] if 'agent_id' in p else [],capability='read' if action=='read' else 'write',allowed_roles=('owner','admin','member') if action=='read' else ('owner','admin'),mutating=action!='read',revision_required=action=='update',audit_fields=('agent_id',) if action!='create' else ('provider_key',)))
