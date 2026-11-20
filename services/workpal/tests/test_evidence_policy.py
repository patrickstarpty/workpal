from django.test import TestCase
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership
from workpal.contracts import Actor, ActionRequest
from workpal.actions.registry import execute

class EvidencePolicyTests(TestCase):
    def setUp(self):
        u=get_user_model().objects.create(username='policy-owner')
        w=Workspace.objects.create(name='policy-workspace')
        Membership.objects.create(user=u,workspace=w,role='owner')
        self.actor=Actor(u.pk,w.pk)
        def call(name,payload,key):
            return execute(self.actor,ActionRequest(name,payload,None,key)).data
        p=call('project.create',{'name':'p'},'p')['id']
        e=call('environment.create',dict(project_id=p,name='SIT',timezone='UTC'),'e')['id']
        s=call('environment_service.create',dict(environment_id=e,name='s'),'s')['id']
        self.source=call('evidence_source.create_upload',dict(environment_id=e,name='upload',allowed_services=[s]),'src')['id']
        self.policy=dict(version=1,allow_text=True,allow_fields=['message'],redact_literals=['SECRET-literal'])

    def test_policy_registered_configuration_and_secrecy(self):
        payload=dict(source_id=self.source,policy=self.policy)
        pending=execute(self.actor,ActionRequest('evidence_policy.configure',payload,1,'policy'))
        self.assertEqual(pending.state,'waiting_confirmation')
        result=execute(self.actor,ActionRequest('evidence_policy.configure',payload,1,'policy',confirmation_id=pending.data['confirmation_id']))
        self.assertEqual(result.data['revision'],2)
        from workpal.investigation.models import Source, EvidencePolicyVersion
        source=Source.objects.get(pk=self.source)
        self.assertEqual(source.current_policy_id,EvidencePolicyVersion.objects.get().pk)
        self.assertEqual(source.policy_revision,2)
        dto=execute(self.actor,ActionRequest('evidence_source.read',{'source_id':self.source},None,None)).data
        self.assertEqual(set(dto),{'id','environment_id','name','adapter_type','allowed_services'})
        from django.apps import apps
        for label in ('actions.Confirmation','actions.IdempotencyResult','audit.AuditEvent','audit.Outbox'):
            model=apps.get_model(label)
            self.assertNotIn('SECRET-literal',str(list(model.objects.values())))

    def request(self,key='policy',revision=1):
        return ActionRequest('evidence_policy.configure',dict(source_id=self.source,policy=self.policy),revision,key)

    def confirmed(self,key='policy',revision=1):
        request=self.request(key,revision)
        request.confirmation_id=execute(self.actor,request).data['confirmation_id']
        return request

    def snapshot(self):
        from django.apps import apps
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()}

    def test_unconfigured_validation_versions_and_copy(self):
        from copy import deepcopy
        from workpal.contracts import DomainError
        from workpal.investigation.evidence import configure_policy,read_policy
        from workpal.investigation.models import EvidencePolicyVersion
        self.assertEqual(read_policy(self.actor,self.source),dict(source_id=self.source,revision=1,configured=False,policy_sha256=''))
        before=self.snapshot()
        for value in (True,0,-1,'1',2**63,None):
            with self.assertRaises(DomainError): configure_policy(self.actor,value,self.policy,1)
            with self.assertRaises(DomainError): configure_policy(self.actor,self.source,self.policy,value)
        for policy in (None,{},dict(self.policy,extra=True),dict(self.policy,version=True),dict(self.policy,allow_text=1),dict(self.policy,allow_fields=['x','x']),dict(self.policy,redact_literals=['']),dict(self.policy,allow_fields=['SECRET-literal'])):
            with self.assertRaises(DomainError): configure_policy(self.actor,self.source,policy,1)
        for value in (True,0,-1,'1',2**63,None):
            with self.assertRaises(DomainError):
                execute(self.actor,ActionRequest('evidence_policy.configure',dict(source_id=value,policy=self.policy),1,'invalid-id'))
            with self.assertRaises(DomainError):
                execute(self.actor,self.request('invalid-revision',value))
        for policy in ({},dict(self.policy,extra=True),dict(self.policy,version=True),dict(self.policy,allow_text=1)):
            with self.assertRaises(DomainError):
                execute(self.actor,ActionRequest('evidence_policy.configure',dict(source_id=self.source,policy=policy),1,'invalid-policy'))
        self.assertEqual(before,self.snapshot())
        original=deepcopy(self.policy)
        configure_policy(self.actor,self.source,self.policy,1)
        self.policy['redact_literals'].append('new')
        configure_policy(self.actor,self.source,self.policy,2)
        self.assertEqual(EvidencePolicyVersion.objects.get(revision=2).policy,original)
        with self.assertRaises(DomainError): configure_policy(self.actor,self.source,self.policy,1)
        self.assertEqual(EvidencePolicyVersion.objects.count(),2)

    def test_roles_cross_workspace_waiting_and_replay_revocation(self):
        from workpal.contracts import DomainError
        from workpal.investigation.evidence import configure_policy,read_policy
        from workpal.access.models import SourceGrant
        request=self.confirmed()
        member=Membership.objects.get(user_id=self.actor.user_id)
        for role in ('member','admin','owner'):
            member.role=role;member.save()
            if role=='member':
                with self.assertRaises(DomainError): read_policy(self.actor,self.source)
                with self.assertRaises(DomainError): execute(self.actor,request)
                with self.assertRaises(DomainError): configure_policy(self.actor,self.source,self.policy,1)
            else: self.assertFalse(read_policy(self.actor,self.source)['configured'])
        other=Workspace.objects.create(name='other')
        Membership.objects.create(user_id=self.actor.user_id,workspace=other,role='owner')
        with self.assertRaises(DomainError): read_policy(Actor(self.actor.user_id,other.pk),self.source)
        for field in ('publish','write'):
            grants=SourceGrant.objects.filter(user_id=self.actor.user_id)
            grants.update(**{field:False})
            with self.assertRaises(DomainError): execute(self.actor,request)
            with self.assertRaises(DomainError): read_policy(self.actor,self.source)
            grants.update(**{field:True})
        execute(self.actor,request)
        SourceGrant.objects.filter(user_id=self.actor.user_id).update(publish=False)
        with self.assertRaises(DomainError): execute(self.actor,request)
        SourceGrant.objects.filter(user_id=self.actor.user_id).update(publish=True,write=False)
        with self.assertRaises(DomainError): execute(self.actor,request)
        SourceGrant.objects.filter(user_id=self.actor.user_id).update(write=True)
        machine=Actor(self.actor.user_id,self.actor.workspace_id,executor_id='machine')
        with self.assertRaises(DomainError): execute(machine,request)

    def test_record_failure_rolls_back_and_same_key_retries(self):
        from unittest.mock import patch
        from workpal.actions import registry
        from workpal.contracts import DomainError
        request=self.confirmed()
        before=self.snapshot()
        original=registry.record
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise DomainError('storage_unavailable','Storage unavailable.',status=503)
        with patch.object(registry,'record',side_effect=fail):
            with self.assertRaises(DomainError) as caught: execute(self.actor,request)
        self.assertEqual(caught.exception.status,503)
        self.assertEqual(before,self.snapshot())
        execute(self.actor,request)
        after=self.snapshot()
        execute(self.actor,request)
        self.assertEqual(after,self.snapshot())

    def test_management_read_only_access_audit(self):
        from workpal.investigation.evidence import read_policy
        execute(self.actor,self.confirmed())
        before=self.snapshot()
        self.assertEqual(read_policy(self.actor,self.source)['policy'],self.policy)
        self.assertEqual(before,self.snapshot())
        result=execute(self.actor,ActionRequest('evidence_policy.read',{'source_id':self.source},None,None))
        self.assertEqual(result.data['policy'],self.policy)
        after=self.snapshot()
        for label in before:
            if label!='audit.AuditEvent': self.assertEqual(before[label],after[label],label)
        self.assertEqual(len(after['audit.AuditEvent']),len(before['audit.AuditEvent'])+1)

from django.test import TransactionTestCase

class EvidencePolicyConcurrencyTests(TransactionTestCase):
    setUp=EvidencePolicyTests.setUp
    request=EvidencePolicyTests.request
    confirmed=EvidencePolicyTests.confirmed

    def test_independent_confirmations_two_connections_one_revision(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from workpal.contracts import DomainError
        from workpal.investigation.models import Source,EvidencePolicyVersion
        from workpal.actions.models import Confirmation,IdempotencyResult
        from workpal.audit.models import AuditEvent,Outbox
        requests=[self.confirmed('race-a'),self.confirmed('race-b')]
        barrier=Barrier(2)
        def run(request):
            connections.close_all()
            connection=connections['default']
            connection.ensure_connection()
            identity=id(connection.connection)
            barrier.wait(timeout=10)
            try:
                result=execute(self.actor,request)
                return identity,result.state
            except DomainError as error: return identity,error.status
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,requests))
        self.assertEqual(len({row[0] for row in results}),2)
        self.assertCountEqual([row[1] for row in results],['completed',409])
        self.assertEqual(EvidencePolicyVersion.objects.count(),1)
        source=Source.objects.get(pk=self.source)
        self.assertEqual(source.policy_revision,2)
        self.assertEqual(source.current_policy_id,EvidencePolicyVersion.objects.get().pk)
        self.assertEqual(Confirmation.objects.filter(consumed=True).count(),1)
        self.assertEqual(IdempotencyResult.objects.filter(action_id='evidence_policy.configure').count(),1)
        self.assertEqual(AuditEvent.objects.filter(action_id='evidence_policy.configure').count(),1)
        self.assertEqual(Outbox.objects.filter(action_id='evidence_policy.configure').count(),1)
