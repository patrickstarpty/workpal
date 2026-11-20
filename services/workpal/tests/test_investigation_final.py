"""Final investigation acceptance through public interfaces and real transport."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
from unittest.mock import patch
from django.apps import apps
from django.db import connections
from django.test import Client, TransactionTestCase, override_settings
from django.contrib.auth import get_user_model
from workpal.contracts import Actor, ActionRequest, DomainError, ObjectRef
from workpal.identity.models import Workspace, Membership
from workpal.work import service as projects
from workpal.investigation import environments as e, service as s, sources
from workpal.actions import registry
from workpal.actions.models import Confirmation
from workpal.access.service import register_object, resolve
from workpal.access.models import SourceGrant

class InvestigationFinal(TransactionTestCase):
    def setUp(self):
        self.u=get_user_model().objects.create_user(username='final',password='password-final')
        self.w=Workspace.objects.create(name='final')
        Membership.objects.create(user=self.u,workspace=self.w,role='owner')
        self.a=Actor(self.u.pk,self.w.pk)
        self.p=projects.create(self.a,'p')['id']
        self.env=e.create(self.a,self.p,'SIT','UTC')['id']
        self.svc=s.create_service(self.a,self.env,'web')['id']
        self.source=sources.create_upload(self.a,self.env,'upload',[self.svc])
    def request(self,action,payload,key='key',revision=None):
        return ActionRequest(action,payload,revision,key)
    def grant_request(self,user,key='grant'):
        return self.request('environment.grant',dict(environment_id=self.env,user_id=user,read=True,write=True,publish=True),key,e.read(self.a,self.env)['revision'])
    def confirm(self,request):
        token=registry.execute(self.a,request).data['confirmation_id']
        return replace(request,confirmation_id=token)
    def start_request(self,key='start'):
        return self.request('investigation.start',dict(project_id=self.p,environment_id=self.env,service_id=self.svc,problem='private-final-problem',key=key),key)
    def member(self,name):
        u=get_user_model().objects.create_user(username=name)
        Membership.objects.create(user=u,workspace=self.w,role='owner')
        return u
    @override_settings(ALLOWED_HOSTS=['testserver'])
    def test_01_http_nonempty_sources(self):
        c=Client(enforce_csrf_checks=True)
        self.assertEqual(c.get('/api/v1/actions',{'workspace_id':self.w.pk}).status_code,403)
        token=c.get('/api/v1/auth/csrf').json()['csrf_token']
        old=c.cookies['csrftoken'].value
        self.assertEqual(c.post('/api/v1/auth/login',dict(username='final',password='password-final'),content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code,200)
        self.assertNotEqual(old,c.cookies['csrftoken'].value)
        def call(action,payload,key='http',**headers):
            return c.post('/api/v1/actions/'+action,dict(workspace_id=self.w.pk,payload=payload,idempotency_key=key),content_type='application/json',**headers)
        payload=dict(project_id=self.p,name='HTTP',timezone='UTC',source_refs=[dict(kind='project',id=str(self.p))])
        self.assertEqual(call('environment.create',payload).status_code,403)
        self.assertEqual(call('environment.create',payload,HTTP_X_CSRFTOKEN=old).status_code,403)
        headers=dict(HTTP_X_CSRFTOKEN=c.cookies['csrftoken'].value)
        self.assertEqual(call('environment.create',payload,HTTP_HOST='invalid.example',**headers).status_code,400)
        response=call('environment.create',payload,**headers)
        self.assertEqual(response.status_code,200,response.content)
        env=response.json()['data']['id']
        svc=call('environment_service.create',dict(environment_id=env,name='web'),'svc',**headers).json()['data']['id']
        self.assertEqual(call('evidence_source.create_upload',dict(environment_id=env,name='text',allowed_services=[svc]),'source',**headers).status_code,200)
        row=call('investigation.start',dict(project_id=self.p,environment_id=env,service_id=svc,problem='http problem',key='http-start'),'start',**headers).json()['data']
        self.assertEqual(call('investigation.read',dict(investigation_id=row['id']),**headers).json()['data'],row)
        self.assertEqual(call('investigation.list',dict(project_id=self.p,environment_id=env),**headers).json()['data']['items'],[row])
    def test_02_revoke_write_publish(self):
        req=self.start_request(); registry.execute(self.a,req)
        pending=self.confirm(self.grant_request(self.u.pk))
        self.assertIn(dict(kind='environment',id=str(self.env)),Confirmation.objects.get(pk=pending.confirmation_id).scope_refs)
        root=resolve(e.ref(self.env))
        SourceGrant.objects.filter(source=root,user=self.u).update(write=False,publish=False)
        self.assertEqual(e.read(self.a,self.env)['id'],self.env)
        for request in (req,self.start_request('new'),pending):
            with self.assertRaises(DomainError): registry.execute(self.a,request)
        self.assertFalse(Confirmation.objects.get(pk=pending.confirmation_id).consumed)
        SourceGrant.objects.filter(source=root,user=self.u).update(write=True,publish=True)
        upstream_ref=ObjectRef('final_upstream','1')
        register_object(self.w.pk,upstream_ref,is_source=True)
        upstream=resolve(upstream_ref)
        SourceGrant.objects.create(source=upstream,user=self.u,read=True,write=True,publish=True)
        register_object(self.w.pk,projects.ref(self.p),[upstream_ref])
        SourceGrant.objects.filter(source=upstream,user=self.u).update(write=False,publish=False)
        self.assertEqual(e.read(self.a,self.env)['id'],self.env)
        for request in (req,self.start_request('upstream-new')):
            with self.assertRaises(DomainError): registry.execute(self.a,request)
        with self.assertRaises(DomainError): s.start(self.a,self.p,self.env,self.svc,'direct','direct')
    def test_03_self_revoke_and_inactive(self):
        other=self.member('other'); e.grant(self.a,self.env,other.pk,True,True,True,1)
        inactive=self.member('inactive'); inactive.is_active=False; inactive.save()
        with self.assertRaises(DomainError): e.grant(self.a,self.env,inactive.pk,True,False,False,2)
        req=self.request('environment.grant',dict(environment_id=self.env,user_id=self.u.pk,read=False,write=False,publish=False),'self',2)
        req=self.confirm(req)
        self.assertEqual(registry.execute(self.a,req).data,{})
        for fn in (lambda:e.read(self.a,self.env),lambda:registry.execute(self.a,req)):
            with self.assertRaises(DomainError): fn()
        self.assertEqual(e.read(Actor(other.pk,self.w.pk),self.env)['revision'],3)
    def test_04_isolation_pagination_source_read(self):
        other=e.create(self.a,self.p,'UAT','UTC')['id']
        with self.assertRaises(DomainError): s.start(self.a,self.p,other,self.svc,'bad','bad')
        with self.assertRaises(DomainError): sources.create_upload(self.a,other,'bad',[self.svc])
        w=Workspace.objects.create(name='elsewhere'); Membership.objects.create(user=self.u,workspace=w,role='owner')
        with self.assertRaises(DomainError): e.read(Actor(self.u.pk,w.pk),self.env)
        member=self.member('reader'); a=Actor(member.pk,self.w.pk)
        e.grant(self.a,other,member.pk,True,False,False,1)
        self.assertEqual([x['id'] for x in e.list_environments(a,self.p,limit=1)['items']],[other])
        with patch('workpal.investigation.environments.read',side_effect=DomainError('unavailable','unavailable',status=503)):
            with self.assertRaises(DomainError) as caught: e.list_environments(self.a,self.p)
        self.assertEqual(caught.exception.status,503)
        ref=ObjectRef('final_source','1'); register_object(self.w.pk,ref,is_source=True)
        SourceGrant.objects.create(source=resolve(ref),user=self.u,read=True,write=False,publish=False)
        register_object(self.w.pk,sources.source_ref(self.source['id']),[ref])
        s.start(self.a,self.p,self.env,self.svc,'direct','direct')
        registry.execute(self.a,self.start_request())
        from workpal.audit.models import Outbox
        before=Outbox.objects.count()
        registry.execute(self.a,self.request('environment.read',dict(environment_id=self.env)))
        self.assertEqual(before,Outbox.objects.count())
        self.assertNotIn('private-final-problem',str(list(Outbox.objects.values())))
        from workpal.audit.models import AuditEvent
        self.assertNotIn('private-final-problem',str(list(AuditEvent.objects.values())))
        self.assertIn(dict(kind='final_source',id='1'),AuditEvent.objects.get(action_id='investigation.start').scope_refs)
    def snapshot(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('investigation','access','actions','audit')}
    def test_05_actual_record_rollback(self):
        original=registry.record
        def fail(*args):
            original(*args)
            raise DomainError('unavailable','unavailable',status=503)
        requests=[self.request('environment.create',dict(project_id=self.p,name='rollback',timezone='UTC'),'rollback'),self.confirm(self.grant_request(self.u.pk)),self.start_request()]
        for request in requests:
            before=self.snapshot()
            with patch('workpal.actions.registry.record',side_effect=fail):
                with self.assertRaises(DomainError) as caught: registry.execute(self.a,request)
            self.assertEqual(caught.exception.status,503)
            self.assertEqual(before,self.snapshot())
            result=registry.execute(self.a,request)
            after=self.snapshot(); self.assertEqual(registry.execute(self.a,request).data,result.data); self.assertEqual(after,self.snapshot())
    def test_06_two_connection_grants(self):
        users=[self.member('one'),self.member('two')]
        requests=[self.confirm(self.grant_request(u.pk,str(u.pk))) for u in users]
        gate=threading.Barrier(2)
        def run(request):
            connections.close_all(); gate.wait()
            try:
                registry.execute(self.a,request); return 200
            except DomainError as exc: return exc.status
            finally: connections.close_all()
        with ThreadPoolExecutor(2) as pool: results=list(pool.map(run,requests))
        self.assertEqual(sorted(results),[200,409])
        from workpal.audit.models import AuditEvent, Outbox
        self.assertEqual(AuditEvent.objects.filter(action_id='environment.grant').count(),1)
        self.assertEqual(Outbox.objects.filter(action_id='environment.grant').count(),1)
        self.assertEqual(Confirmation.objects.filter(consumed=True).count(),1)
        self.assertEqual(SourceGrant.objects.filter(source=resolve(e.ref(self.env)),user__in=users,read=True).count(),1)
