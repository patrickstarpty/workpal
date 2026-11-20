from django import forms
from workpal.actions.schemas import StructuredField
from workpal.actions.contracts import ActionSpec
from workpal.actions.registry import register
from workpal.contracts import ActionResult
from workpal.work.actions import obj,VIEW as PROJECT
from workpal.work.issue_actions import VIEW as ISSUE,HISTORY,SNAP
from workpal.work.resource_actions import VIEW as RESOURCE,SOURCES
from workpal.agents.actions import VIEW as AGENT
from . import service
S={'type':'string'}; I={'type':'integer'}
SUBJECT=obj(dict(type={'type':'string','enum':['issue']},id={'type':'integer','minimum':1}))
SNAPSHOT=obj(dict(issue=ISSUE,requirements=HISTORY,project=PROJECT,resources={'type':'array','items':RESOURCE},workflow=SNAP,agent=AGENT,source_refs=SOURCES))
# Reason is always structured, including when cancellation clears deferral.
VIEW=obj(dict(id=I,subject=SUBJECT,agent_id=I,status=S,revision=I,input_snapshot=SNAPSHOT,sha256=S,created_at=S,deferred_reason=obj(dict(code=S))))
class Start(forms.Form):
    subject=StructuredField(schema=SUBJECT)
    agent_id=forms.IntegerField(min_value=1)
    key=forms.CharField(max_length=200,strip=False)
    trigger=forms.ChoiceField(choices=[('manual','manual')],required=False)
class Select(forms.Form): run_id=forms.IntegerField(min_value=1)
def register_actions():
    for action,form in [('start',Start),('read',Select),('cancel',Select)]:
        def resolve(actor,p,action=action):
            if action=='start':
                issue=service.issues.read(actor,p['subject']['id'])
                return service.admission_refs(actor,issue,p['agent_id'],p['key'])
            return [service.ref(p['run_id'])]
        def handler(actor,p,revision,action=action):
            if action=='start': data=service.start(actor,**{**p,'trigger':p['trigger'] or 'manual'})
            elif action=='read': data=service.read(actor,**p)
            else: data=service.control(actor,p['run_id'],'cancel',revision)
            return ActionResult('completed',[service.ref(data['id'])],data)
        register(ActionSpec('run.'+action,form,VIEW,handler,resolve,capability='read' if action=='read' else 'write',mutating=action!='read',revision_required=action=='cancel',audit_fields=('agent_id',) if action=='start' else ('run_id',)))
