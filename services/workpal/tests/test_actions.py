from django.test import TestCase
from django import forms
from tests.access_support import AccessFixtures
from workpal.contracts import ActionRequest, ActionResult, DomainError
from workpal.actions import registry
from workpal.actions.contracts import ActionSpec

class Input(forms.Form):
    name = forms.CharField(max_length=30)
    count = forms.IntegerField(required=False)

def restore_catalog(previous):
    registry._specs.clear()
    registry._specs.update(previous)

class ActionTests(AccessFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(restore_catalog, registry._specs.copy())
        registry._specs.clear()
        self.calls = 0
        def handler(actor, payload, revision):
            self.calls += 1
            return ActionResult('completed', [], {'name': payload['name']})
        registry.register(ActionSpec('record', Input, {'type':'object','properties':{'name':{'type':'string'}},'required':['name'],'additionalProperties':False}, handler, lambda a,p: [], 'write', ('member',), True))
    def act(self, payload=None, key='key', revision=None):
        return registry.execute(self.actor, ActionRequest('record', payload or {'name':'x'}, revision, key))
    def test_replay(self):
        self.assertEqual(self.act(), self.act())
        self.assertEqual(self.calls, 1)
    def test_conflict(self):
        self.act()
        with self.assertRaises(DomainError) as e: self.act({'name':'y'})
        self.assertEqual(e.exception.status,409)
    def test_revision_conflict(self):
        self.act()
        with self.assertRaises(DomainError): self.act(revision=2)
    def test_extra(self):
        with self.assertRaises(DomainError): self.act({'name':'x','extra':1})
    def test_types(self):
        for payload in ({'name':3},{'name':[]},{'name':'x','count':True},{'name':'x','count':'3'}):
            with self.assertRaises(DomainError): self.act(payload)
    def test_catalog(self):
        self.assertEqual(len(registry.catalog(self.actor)),1)
        self.member.role='admin'; self.member.save()
        self.assertEqual(registry.catalog(self.actor),[])
    def test_events(self):
        from workpal.audit.models import AuditEvent, Outbox
        self.act(); self.act()
        self.assertEqual(AuditEvent.objects.count(),1)
        self.assertEqual(Outbox.objects.count(),1)
    def test_unknown(self):
        with self.assertRaises(DomainError): registry.execute(self.actor,ActionRequest('missing',{},None,None))
    def test_confirmation(self):
        from dataclasses import replace
        registry._specs['record']=replace(registry._specs['record'],confirmation_required=True)
        self.assertEqual(self.act().state,'waiting_confirmation')
        self.assertEqual(self.calls,0)
    def test_rollback(self):
        from dataclasses import replace
        from workpal.identity.models import Workspace
        from workpal.audit.models import AuditEvent,Outbox
        from workpal.actions.models import IdempotencyResult
        def fail(*args):
            Workspace.objects.create(name='rolled back')
            raise RuntimeError('failure')
        registry._specs['record']=replace(registry._specs['record'],handler=fail)
        with self.assertRaises(RuntimeError): self.act()
        self.assertFalse(Workspace.objects.filter(name='rolled back').exists())
        self.assertEqual((AuditEvent.objects.count(),Outbox.objects.count(),IdempotencyResult.objects.count()),(0,0,0))
    def test_source_revocation(self):
        from dataclasses import replace
        grant=self.grant(self.a,read=True,write=True)
        registry._specs['record']=replace(registry._specs['record'],resolve_refs=lambda a,p:[self.a])
        self.act()
        grant.delete()
        with self.assertRaises(DomainError): self.act()
    def test_result_revocation(self):
        from dataclasses import replace
        self.grant(self.a,read=True)
        registry._specs['record']=replace(registry._specs['record'],handler=lambda *args:ActionResult('completed',[self.direct],{'name':'x'}))
        self.act()
        from workpal.access.models import SourceGrant
        SourceGrant.objects.all().delete()
        with self.assertRaises(DomainError): self.act()
    def test_cross_workspace(self):
        from dataclasses import replace
        from workpal.contracts import ObjectRef
        ref=self.register(self.other.pk,ObjectRef('record','foreign'))
        registry._specs['record']=replace(registry._specs['record'],resolve_refs=lambda a,p:[ref])
        with self.assertRaises(DomainError): self.act()
    def test_schema(self):
        from workpal.actions.schemas import form_schema,validate
        schema=form_schema(Input)
        validate({'name':'ok','count':3},schema)
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['name']['maxLength'],30)
    def test_unsupported_schema(self):
        from dataclasses import replace
        with self.assertRaises(ValueError): registry.register(replace(registry._specs['record'],action_id='bad',output_schema={'type':'object'}))

from django.test import TransactionTestCase
class ConcurrentActions(AccessFixtures,TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(restore_catalog, registry._specs.copy())

    def test_real_connections(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from workpal.identity.models import Workspace
        from workpal.audit.models import AuditEvent,Outbox
        registry._specs.clear()
        def handler(actor,payload,revision):
            Workspace.objects.create(name='effect')
            return ActionResult('completed',[],{'name':'x'})
        registry.register(ActionSpec('parallel',Input,{'type':'object','properties':{'name':{'type':'string'}},'required':['name'],'additionalProperties':False},handler,lambda a,p:[],mutating=True))
        barrier=Barrier(2)
        def execute():
            connections.close_all()
            try:
                barrier.wait()
                return registry.execute(self.actor,ActionRequest('parallel',{'name':'x'},None,'same'))
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:execute(),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(Workspace.objects.filter(name='effect').count(),1)
        self.assertEqual(AuditEvent.objects.count(),1)
        self.assertEqual(Outbox.objects.count(),1)
