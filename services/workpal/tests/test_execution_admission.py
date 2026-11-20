from tests.support import WorkpalCase
from tests.access_support import AccessFixtures
from workpal.contracts import DomainError,Actor
from workpal.agents import service as agents
from workpal.execution import service as runs
from workpal.work import service as projects,issues,resources
from unittest.mock import patch

from django.test import TransactionTestCase
class Admission(AccessFixtures,TransactionTestCase):
    act=WorkpalCase.act
    def setUp(self):
        super().setUp(); self.member.role='owner'; self.member.save()
        self.project=projects.create(self.actor,'Project')
        self.issue=issues.create(self.actor,self.project['id'],'Task')
        self.agent=agents.create(self.actor,'Builder')
        self.subject={'type':'issue','id':self.issue['id']}
    def start(self,key='start'):
        return runs.start(self.actor,self.subject,self.agent['id'],key)
    def test_durable_close_loop(self):
        r=self.act(self.actor,'run.start',dict(subject=self.subject,agent_id=self.agent['id'],key='intent'),key='http').data
        self.assertEqual(r['status'],'deferred'); self.assertEqual(r['deferred_reason']['code'],'runtime_unavailable')
        from django.db import connection
        connection.close()
        self.assertEqual(self.act(self.actor,'run.read',{'run_id':r['id']}).data,r)
        cancelled=self.act(self.actor,'run.cancel',{'run_id':r['id']},key='cancel',revision=1).data
        self.assertEqual(cancelled['status'],'cancelled')
        self.assertEqual(issues.read(self.actor,self.issue['id']),self.issue)
    def test_frozen_snapshot(self):
        r=self.start(); issues.update(self.actor,self.issue['id'],1,title='Changed')
        agents.update(self.actor,self.agent['id'],1,name='Changed')
        self.assertEqual(runs.read(self.actor,r['id'])['input_snapshot'],r['input_snapshot'])
    def test_intent_and_active_dedup(self):
        r=self.start(); self.assertEqual(self.start(),r); self.assertEqual(self.start('other')['id'],r['id'])
        other=agents.create(self.actor,'Other')
        with self.assertRaises(DomainError) as e: runs.start(self.actor,self.subject,other['id'],'start')
        self.assertEqual(e.exception.status,409)
        runs.control(self.actor,r['id'],'cancel',1)
        self.assertEqual(self.start()['id'],r['id']); self.assertNotEqual(self.start('new')['id'],r['id'])
    def test_cas_and_unavailable_operations(self):
        r=self.start(); runs.control(self.actor,r['id'],'cancel',1)
        for op,rev in [('cancel',1),('retry',2),('resume',2)]:
            with self.assertRaises(DomainError): runs.control(self.actor,r['id'],op,rev)
    def test_current_source_revocation(self):
        self.register(self.workspace.pk,issues.ref(self.issue['id']),[self.a]); g=self.grant(self.a,read=True,write=True)
        r=self.start(); g.read=False; g.save()
        for operation in [self.start,lambda:runs.read(self.actor,r['id']),lambda:runs.control(self.actor,r['id'],'cancel',1)]:
            with self.assertRaises(DomainError) as e: operation()
            self.assertEqual(e.exception.status,403)
    def test_current_membership(self):
        r=self.start(); self.member.delete()
        with self.assertRaises(DomainError): runs.read(self.actor,r['id'])
    def test_workspace_isolation(self):
        r=self.start()
        with self.assertRaises(DomainError): runs.read(Actor(self.user.pk,self.other.pk),r['id'])
    def test_extension_providers(self):
        for provider in agents.PROVIDERS[1:]:
            a=agents.create(self.actor,provider,provider)
            with self.assertRaises(DomainError) as e: runs.start(self.actor,self.subject,a['id'],provider)
            self.assertEqual(e.exception.code,'capability_unavailable')
    def test_unsupported_subject_trigger(self):
        for subject in [{'type':'chat','id':1},{'type':'issue','id':True}]:
            with self.assertRaises(DomainError): runs.start(self.actor,subject,self.agent['id'],'bad')
        with self.assertRaises(DomainError): runs.start(self.actor,self.subject,self.agent['id'],'node','node')
    def test_no_silent_resource_omission(self):
        self.grant(self.a,read=True,write=True)
        resource=resources.create(self.actor,self.project['id'],'Restricted','github','org/repo',source_refs=[{'kind':self.a.kind,'id':self.a.id}])
        from workpal.access.models import SourceGrant
        SourceGrant.objects.filter(user=self.user).delete()
        with self.assertRaises(DomainError): self.start()
    def test_rollback_and_retry(self):
        from workpal.execution.models import Run,Intent
        original=runs.register_object
        def fail(*a,**kw): original(*a,**kw); raise RuntimeError('after write')
        with patch.object(runs,'register_object',side_effect=fail):
            with self.assertRaises(RuntimeError): self.start()
        self.assertEqual(Run.objects.count(),0); self.assertEqual(Intent.objects.count(),0)
        self.assertEqual(self.start()['status'],'deferred')
    def test_two_connections_one_active_run(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from workpal.execution.models import Run,Intent
        barrier=Barrier(2)
        def request(key):
            connections['default'].close(); barrier.wait()
            try: return self.start(key)['id']
            finally: connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(request,'race-a'); b=pool.submit(request,'race-b')
            self.assertEqual(a.result(),b.result())
        self.assertEqual(Run.objects.count(),1); self.assertEqual(Intent.objects.count(),2)
    def test_registry_replay_revoked(self):
        self.register(self.workspace.pk,issues.ref(self.issue['id']),[self.a]); g=self.grant(self.a,read=True,write=True)
        payload=dict(subject=self.subject,agent_id=self.agent['id'],key='intent')
        self.act(self.actor,'run.start',payload,key='registry')
        g.read=False; g.save()
        with self.assertRaises(DomainError): self.act(self.actor,'run.start',payload,key='registry')
