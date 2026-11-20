from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace,Membership
from workpal.contracts import Actor,DomainError,ActionRequest
from workpal.actions.registry import execute
from workpal.investigation import environments as e,service as s,sources
from workpal.work import service as projects
from workpal.investigation.models import Investigation

class InvestigationTests(TransactionTestCase):
    def setUp(self):
        u=get_user_model().objects.create(username='o'); w=Workspace.objects.create(name='w')
        Membership.objects.create(user=u,workspace=w,role='owner'); self.a=Actor(u.pk,w.pk)
        self.p=projects.create(self.a,'p')['id']; self.e=e.create(self.a,self.p,'SIT','UTC')['id']
        self.s=s.create_service(self.a,self.e,'web')['id']
        self.source=sources.create_upload(self.a,self.e,'excerpt',[self.s])
    def start(self,key='k',problem='failure'):
        return s.start(self.a,self.p,self.e,self.s,problem,key)
    def test_persistence_and_intent(self):
        x=self.start(); self.assertEqual(self.start(),x); self.assertEqual(s.read(self.a,x['id']),x)
        with self.assertRaises(DomainError): self.start(problem='different')
        self.assertEqual(Investigation.objects.count(),1)
    def test_independent_environment(self):
        u=get_user_model().objects.create(username='m'); Membership.objects.create(user=u,workspace_id=self.a.workspace_id,role='member'); a=Actor(u.pk,self.a.workspace_id)
        other=e.create(self.a,self.p,'UAT','UTC')['id']
        e.grant(self.a,self.e,u.pk,True,True,False,1)
        x=s.start(a,self.p,self.e,self.s,'failure','m')
        self.assertEqual(s.read(a,x['id'])['status'],'investigating')
        with self.assertRaises(DomainError): e.read(a,other)
        e.grant(self.a,self.e,u.pk,False,False,False,2)
        with self.assertRaises(DomainError): s.start(a,self.p,self.e,self.s,'failure','m')
    def test_mismatch(self):
        other=e.create(self.a,self.p,'UAT','UTC')['id']
        with self.assertRaises(DomainError): sources.create_upload(self.a,other,'bad',[self.s])
        with self.assertRaises(DomainError): s.start(self.a,self.p,other,self.s,'failure','k')
    def test_defaults_and_timezone(self):
        first=e.ensure_defaults(self.a,self.p,'UTC'); self.assertEqual(first,e.ensure_defaults(self.a,self.p,'Asia/Shanghai'))
        with self.assertRaises(DomainError): e.create(self.a,self.p,'bad','not/a/zone')
    def test_registry_and_audit_rollback(self):
        from unittest.mock import patch
        from workpal.audit.models import Outbox
        payload=dict(project_id=self.p,environment_id=self.e,service_id=self.s,problem='secret problem',key='intent')
        request=ActionRequest('investigation.start',payload,None,'registry')
        with patch('workpal.actions.registry.record',side_effect=RuntimeError('after write')):
            with self.assertRaises(RuntimeError): execute(self.a,request)
        self.assertEqual(Investigation.objects.count(),0)
        x=execute(self.a,request); self.assertEqual(execute(self.a,request).data,x.data)
        self.assertNotIn('secret problem',str(list(Outbox.objects.values())))
    def test_two_connections(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import connections
        import threading
        gate=threading.Barrier(2)
        def run(_):
            connections.close_all(); gate.wait()
            try: return self.start()['id']
            finally: connections.close_all()
        with ThreadPoolExecutor(2) as pool: ids=list(pool.map(run,range(2)))
        self.assertEqual(ids[0],ids[1]); self.assertEqual(Investigation.objects.count(),1)
    def test_visible_pagination(self):
        u=get_user_model().objects.create(username='m'); Membership.objects.create(user=u,workspace_id=self.a.workspace_id,role='member'); a=Actor(u.pk,self.a.workspace_id)
        visible=e.create(self.a,self.p,'custom','UTC')['id']; e.grant(self.a,visible,u.pk,True,False,False,1)
        self.assertEqual([x['id'] for x in e.list_environments(a,self.p,limit=1)['items']],[visible])
    def test_input_and_read_no_outbox(self):
        from workpal.audit.models import Outbox
        for problem in ('','x'*8001):
            with self.assertRaises(DomainError): self.start(problem=problem)
        x=self.start(); before=Outbox.objects.count(); s.read(self.a,x['id']); self.assertEqual(Outbox.objects.count(),before)
