from django.test import TestCase
from workpal.contracts import ActionRequest,DomainError
from workpal.actions.registry import execute
from tests import test_evidence_policy as policy_fixtures
from workpal.investigation import query_config

class QueryConfigurationTests(TestCase):
    snapshot=policy_fixtures.EvidencePolicyTests.snapshot
    def setUp(self):
        policy_fixtures.EvidencePolicyTests.setUp(self)
        from workpal.investigation.models import Source
        upload=Source.objects.get(pk=self.source)
        self.upload=self.source
        self.source=execute(self.actor,ActionRequest('evidence_source.create_query',dict(environment_id=upload.environment_id,name='query',allowed_services=list(upload.allowed_services.values_list('pk',flat=True))),None,'query-source')).data['id']
        self.config=dict(version=1,endpoint='https://logs.example.com/search',method='GET',network_zone='public',secret_ref='opaque-ref',capabilities=['search_logs'],parameter_schema='search_logs_v1',response_mapping='jsonl_logs_v1',readonly_proof=dict(reference='manual review',sha256='a'*64,attestation='Human reviewed protocol'))
    def confirmed(self,action,value,key,revision=1):
        r=ActionRequest(action,dict(source_id=self.source,**value),revision,key)
        pending=execute(self.actor,r)
        self.assertEqual(pending.state,'waiting_confirmation')
        r.confirmation_id=pending.data['confirmation_id']
        return r
    def configure(self):
        execute(self.actor,self.confirmed('query_policy.configure',dict(policy=self.policy),'policy'))
        return self.confirmed('query_config.configure',dict(config=self.config),'config')
    def test_registry_source_types(self):
        for pk,kind in ((self.source,'http_query'),(self.upload,'upload')):
            self.assertEqual(execute(self.actor,ActionRequest('evidence_source.read',dict(source_id=pk),None,None)).data['adapter_type'],kind)
    def test_configuration_confirmation_copy_and_versions(self):
        from workpal.investigation.models import SourceQueryVersion
        r=self.configure(); result=execute(self.actor,r)
        self.assertEqual(result.data['revision'],2)
        self.config['readonly_proof']['reference']='changed'
        self.assertEqual(SourceQueryVersion.objects.get().config['readonly_proof']['reference'],'manual review')
        dto=query_config.read_config(self.actor,self.source)
        self.assertEqual(set(dto),{'source_id','revision','config_sha256','configured','connected'})
        self.assertFalse(dto['connected'])
    def test_permissions_and_cached_revocation(self):
        from workpal.identity.models import Membership
        r=self.configure()
        from workpal.access.models import SourceGrant
        from workpal.contracts import Actor
        from workpal.identity.models import Workspace
        for field in ('write','publish'):
            SourceGrant.objects.filter(user_id=self.actor.user_id).update(**{field:False})
            with self.assertRaises(DomainError): execute(self.actor,r)
            with self.assertRaises(DomainError): query_config.read_config(self.actor,self.source)
            SourceGrant.objects.filter(user_id=self.actor.user_id).update(**{field:True})
        with self.assertRaises(DomainError): query_config.read_config(Actor(self.actor.user_id,self.actor.workspace_id,executor_id='machine'),self.source)
        other=Workspace.objects.create(name='other-query')
        Membership.objects.create(user_id=self.actor.user_id,workspace=other,role='owner')
        with self.assertRaises(DomainError): query_config.read_config(Actor(self.actor.user_id,other.pk),self.source)
        execute(self.actor,r)
        Membership.objects.filter(user_id=self.actor.user_id).update(role='member')
        with self.assertRaises(DomainError): execute(self.actor,r)
        with self.assertRaises(DomainError): query_config.read_config(self.actor,self.source)
    def test_closed_config_and_revision(self):
        query_config.configure_policy(self.actor,self.source,self.policy,1)
        before=self.snapshot()
        for value in (True,0,-1,'1',None,2**63):
            with self.assertRaises(DomainError): query_config.configure(self.actor,self.source,self.config,value)
        from copy import deepcopy
        variants=[dict(self.config,extra=True),dict(self.config,version=True)]
        for url in ('http://logs.example.com/x','https://user@logs.example.com/x','https://127.0.0.1/x','https://logs.example.com:444/x','https://logs.example.com/../x','https://logs.example.com/%20','https://logs.example.com/x?x=1'):
            variants.append(dict(self.config,endpoint=url))
        for config in variants:
            with self.assertRaises(DomainError) as caught: query_config.configure(self.actor,self.source,config,1)
            self.assertEqual((caught.exception.code,caught.exception.status),('invalid_input',400))
            self.assertEqual(before,self.snapshot())
    def test_record_failure_rolls_back_and_retry(self):
        from unittest.mock import patch
        from workpal.actions import registry
        r=self.configure(); before=self.snapshot(); original=registry.record
        def fail(*a,**kw):
            original(*a,**kw)
            raise DomainError('storage_unavailable','Unavailable',status=503)
        with patch.object(registry,'record',side_effect=fail):
            with self.assertRaises(DomainError): execute(self.actor,r)
        self.assertEqual(before,self.snapshot())
        execute(self.actor,r); after=self.snapshot(); execute(self.actor,r); self.assertEqual(after,self.snapshot())
    def test_policy_required(self):
        with self.assertRaises(DomainError) as caught: query_config.configure(self.actor,self.source,self.config,1)
        self.assertEqual(caught.exception.code,'policy_required')

from django.test import TransactionTestCase
class QueryConfigurationConcurrencyTests(TransactionTestCase):
    setUp=QueryConfigurationTests.setUp
    confirmed=QueryConfigurationTests.confirmed
    def test_two_connections_same_revision(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from workpal.investigation.models import Source,SourceQueryVersion
        from workpal.actions.models import Confirmation,IdempotencyResult
        from workpal.audit.models import AuditEvent,Outbox
        execute(self.actor,self.confirmed('query_policy.configure',dict(policy=self.policy),'policy'))
        requests=[self.confirmed('query_config.configure',dict(config=self.config),key) for key in ('race-a','race-b')]
        barrier=Barrier(2)
        def run(request):
            connections.close_all(); connection=connections['default']; connection.ensure_connection(); identity=id(connection.connection)
            barrier.wait(timeout=10)
            try: return identity,execute(self.actor,request).state
            except DomainError as error: return identity,error.status
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(run,requests))
        self.assertEqual(len({r[0] for r in results}),2)
        self.assertCountEqual([r[1] for r in results],['completed',409])
        self.assertEqual(SourceQueryVersion.objects.count(),1)
        source=Source.objects.get(pk=self.source)
        self.assertEqual(source.query_revision,2)
        self.assertEqual(source.current_query_config_id,SourceQueryVersion.objects.get().pk)
        self.assertEqual(Confirmation.objects.filter(action_id='query_config.configure',consumed=True).count(),1)
        for model in (IdempotencyResult,AuditEvent,Outbox): self.assertEqual(model.objects.filter(action_id='query_config.configure').count(),1)
