"""Strict action forms and DTO adapters; business policy lives in service."""
from django import forms
from workpal.actions.schemas import StructuredField
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from . import service, contracts as c

def identifier(): return forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER-1)
class Issue(forms.Form):
    issue_id=identifier()
class Comment(forms.Form):
    comment_id=identifier()
class Notification(forms.Form):
    notification_id=identifier()
class Create(Issue):
    body=forms.CharField(max_length=20000,strip=False)
    mention_user_ids=StructuredField(schema=dict(type='array',maxItems=50,items=dict(type='integer',minimum=1,maximum=MAX_SQLITE_INTEGER-1)),required=False)
    source_refs=StructuredField(schema=dict(type='array',maxItems=50,items=c.obj(dict(kind=dict(type='string',minLength=1),id=dict(type='string',minLength=1)))),required=False)
class Update(Comment):
    body=forms.CharField(max_length=20000,strip=False,required=False)
    mention_user_ids=Create.base_fields["mention_user_ids"]
    source_refs=Create.base_fields["source_refs"]
    def clean(self):
        data=super().clean()
        for key in ("body","mention_user_ids","source_refs"):
            if key not in self.data: data.pop(key,None)
        if not any(key in data for key in ("body","mention_user_ids","source_refs")): raise forms.ValidationError("Change required.")
        return data
class Page(forms.Form):
    cursor=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER-1,required=False)
    limit=forms.IntegerField(min_value=1,max_value=200,required=False)
class Comments(Issue,Page):
    include_archived=forms.BooleanField(required=False)
class Inbox(Page):
    unread_only=forms.BooleanField(required=False)

def register_actions():
    from workpal.actions.registry import register
    definitions=[('comment.update',Update,c.COMMENT,True,'write'),('comment.remove',Comment,c.COMMENT,True,'write'),('comment.restore',Comment,c.COMMENT,True,'write'),('comment.create',Create,c.COMMENT,True,'write'),('comment.read',Comment,c.COMMENT,False,'read'),
        ('comment.list',Comments,c.page(c.COMMENT),False,'read'),
        ('issue.subscribe',Issue,c.SUBSCRIPTION,True,'read'),('issue.unsubscribe',Issue,c.SUBSCRIPTION,True,'read'),
        ('issue.subscription.read',Issue,c.SUBSCRIPTION,False,'read'),
        ('inbox.list',Inbox,c.page(c.NOTIFICATION),False,'read'),('inbox.mark_read',Notification,c.NOTIFICATION,True,'read'),('inbox.mark_unread',Notification,c.NOTIFICATION,True,'read')]
    for name,form,schema,mutating,capability in definitions:
        def resolve(actor,p,name=name):
            if name in ('comment.update','comment.remove','comment.restore'): return service.management_refs(actor,**p)
            if name=='comment.create': return service.create_refs(actor,p['issue_id'],p.get('source_refs'))
            if name=='comment.read': return [service.ref(service.selected(actor,p['comment_id']).pk)]
            if name in ('inbox.mark_read','inbox.mark_unread'): return [service.ref(service.selected(actor,p['notification_id'],True).pk,True)]
            if 'issue_id' in p:
                service.issues.read(actor,p['issue_id'])
                return [service.issues.ref(p['issue_id'])]
            return []
        def run(actor,p,revision,name=name):
            if name=='comment.create': data=service.create(actor,**p)
            elif name in ('comment.update','comment.remove','comment.restore'): data=service.manage(actor,revision=revision,operation=name.split('.')[1],**p)
            elif name=='comment.read': data=service.read(actor,**p)
            elif name in ('inbox.mark_read','inbox.mark_unread'): data=getattr(service, name.split('.')[1])(actor,revision=revision,**p)
            elif name in ('comment.list','inbox.list'):
                data=service.listing(actor,**{**p,'cursor':p.get('cursor') or 0,'limit':p.get('limit') or 50})
            else: data=service.subscription(actor,p['issue_id'],{'issue.subscribe':True,'issue.unsubscribe':False}.get(name))
            if name.startswith('issue.'): refs=[service.issues.ref(data['issue_id'])]
            elif 'items' in data: refs=[service.ref(item['id'],name=='inbox.list') for item in data['items']]
            else: refs=[service.ref(data['id'],name in ('inbox.mark_read','inbox.mark_unread'))]
            return ActionResult('completed',refs,data)
        register(ActionSpec(name,form,schema,run,resolve,capability=capability,mutating=mutating,
            confirmation_required=name=='comment.remove',
            revision_required=name in ('comment.update','comment.remove','comment.restore','inbox.mark_read','inbox.mark_unread'),audit_fields=tuple(form.base_fields)))
