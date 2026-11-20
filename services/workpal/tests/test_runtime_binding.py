from django.test import TestCase
from tests import test_runtime_http as fixtures
from workpal.contracts import Actor
from workpal.agents.models import Agent

class RuntimeBindingTests(TestCase):
    setUp = fixtures.RuntimeHTTPTests.setUp
    post = fixtures.RuntimeHTTPTests.post
    paired = fixtures.RuntimeHTTPTests.paired
    execute = fixtures.RuntimeHTTPTests.execute

    def test_bind_public_registry(self):
        _, runtime = self.paired()
        from workpal.agents.service import create
        agent = Agent.objects.get(pk=create(Actor(self.user.pk,self.workspace.pk), 'Bound')['id'])
        result = self.execute('runtime.bind', dict(agent_id=agent.pk, runtime_id=runtime['runtime_id']), 1, 'bind')
        self.assertEqual(result.data, dict(agent_id=agent.pk, runtime_id=runtime['runtime_id'], revision=2, binding_revision=1, enabled=True))

    def test_roundtrip_replay(self):
        from workpal.audit.models import AuditEvent
        agent, runtime = self.fixture()
        payload = dict(agent_id=agent, runtime_id=runtime)
        first = self.execute('runtime.bind', payload, 1, 'one')
        self.assertEqual(self.execute('runtime.bind', payload, 1, 'one').data, first.data)
        self.execute('runtime.bind', payload, 2, 'two')
        last = self.execute('runtime.unbind', dict(agent_id=agent), 3, 'off')
        self.assertEqual(last.data['binding_revision'], 3)
        self.assertFalse(last.data['enabled'])
        self.assertEqual(self.execute('runtime.unbind', dict(agent_id=agent), 3, 'off').data, last.data)
        self.assertEqual(AuditEvent.objects.filter(action_id='runtime.bind').count(), 2)

    def fixture(self):
        from workpal.agents.service import create
        _, runtime = self.paired()
        return create(Actor(self.user.pk,self.workspace.pk), 'Agent')['id'], runtime['runtime_id']

    def test_strict_inputs(self):
        from workpal.contracts import DomainError
        agent, runtime = self.fixture()
        for payload in (dict(agent_id=True,runtime_id=runtime), dict(agent_id=agent,runtime_id=runtime,extra=1)):
            with self.assertRaises(DomainError):
                self.execute('runtime.bind',payload,1,'bad')

    def test_executor_rejected(self):
        from workpal.contracts import DomainError
        agent, runtime = self.fixture()
        with self.assertRaises(DomainError) as error:
            self.execute('runtime.bind',dict(agent_id=agent,runtime_id=runtime),1,'executor',Actor(self.user.pk,self.workspace.pk,''))
        self.assertEqual(error.exception.status,403)

    def test_revoked_target(self):
        from workpal.agents import runtime_identity as core
        from workpal.contracts import DomainError
        agent, runtime = self.fixture()
        core.revoke(Actor(self.user.pk,self.workspace.pk),runtime,1)
        with self.assertRaises(DomainError) as error:
            self.execute('runtime.bind',dict(agent_id=agent,runtime_id=runtime),1,'revoked')
        self.assertEqual(error.exception.code,'capability_unavailable')

    def test_actual_audit_rollback_retry(self):
        from unittest.mock import patch
        from workpal.actions import registry
        from workpal.actions.models import IdempotencyResult
        from workpal.agents.models import RuntimeBinding
        from workpal.audit.models import AuditEvent, Outbox
        from workpal.access.models import RegisteredObject, SourceLink
        from workpal.contracts import DomainError
        agent, runtime = self.fixture()
        models = (Agent, RuntimeBinding, RegisteredObject, SourceLink, IdempotencyResult, AuditEvent, Outbox)
        def snapshot():
            return [list(model.objects.order_by('pk').values()) for model in models]
        before = snapshot()
        original = registry.record
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('storage_unavailable','Unavailable',status=503)
        def run():
            return self.execute('runtime.bind',dict(agent_id=agent,runtime_id=runtime),1,'retry')
        with patch.object(registry,'record',side_effect=fail):
            with self.assertRaises(DomainError) as error: run()
        self.assertEqual(error.exception.status,503)
        self.assertEqual(snapshot(),before)
        result = run()
        self.assertEqual(run().data,result.data)

    def test_sources_current_and_old_target_replay(self):
        from workpal.access.service import register_object
        from workpal.access.models import RegisteredObject, SourceGrant
        from workpal.contracts import ObjectRef, DomainError
        agent, runtime = self.fixture()
        _, second = self.paired()
        grants = []
        for kind, pk in [('agent',agent),('runtime',runtime),('runtime',second['runtime_id'])]:
            source = ObjectRef('source',f'{kind}-{pk}')
            register_object(self.workspace.pk,source,is_source=True)
            grants.append(SourceGrant.objects.create(source=RegisteredObject.objects.get(kind='source',object_id=source.id),user=self.user,read=True,write=True))
            register_object(self.workspace.pk,ObjectRef(kind,str(pk)),[source])
        first = dict(agent_id=agent,runtime_id=runtime)
        self.execute('runtime.bind',first,1,'first')
        for grant in grants:
            for field in ('write','read'):
                setattr(grant,field,False); grant.save()
                with self.assertRaises(DomainError):
                    self.execute('runtime.bind',dict(agent_id=agent,runtime_id=second['runtime_id']),2,'next')
                setattr(grant,field,True); grant.save()
        self.execute('runtime.bind',dict(agent_id=agent,runtime_id=second['runtime_id']),2,'next')
        grants[1].write=False; grants[1].save()
        with self.assertRaises(DomainError): self.execute('runtime.bind',first,1,'first')

    def test_binding_keeps_run_and_providers(self):
        from workpal.agents import service as agents
        from workpal.execution import service as runs
        from workpal.execution.models import Run
        from workpal.work import service as projects, issues
        from workpal.contracts import DomainError
        actor = Actor(self.user.pk,self.workspace.pk)
        agent, runtime = self.fixture()
        project = projects.create(actor,'Project')
        issue = issues.create(actor,project['id'],'Issue')
        subject = dict(type='issue',id=issue['id'])
        old = runs.start(actor,subject,agent,'old')
        before = list(Run.objects.values())
        self.execute('runtime.bind',dict(agent_id=agent,runtime_id=runtime),1,'bound')
        self.assertEqual(list(Run.objects.values()),before)
        runs.control(actor,old['id'],'cancel',1)
        self.assertEqual(runs.start(actor,subject,agent,'new')['status'],'deferred')
        self.assertEqual(agents.read(actor,agent)['provider_key'],'copilot_cli')
        for provider in agents.PROVIDERS[1:]:
            extension = agents.create(actor,provider,provider)
            self.execute('runtime.bind',dict(agent_id=extension['id'],runtime_id=runtime),1,provider)
            self.assertEqual(agents.read(actor,extension['id'])['provider_key'],provider)
            with self.assertRaises(DomainError) as error: runs.start(actor,subject,extension['id'],provider)
            self.assertEqual(error.exception.code,'capability_unavailable')

    def test_roles_tenants_direct_ids_and_revoked_unbind(self):
        from workpal.agents import runtime_identity as core
        from workpal.identity.models import Membership, Workspace
        from workpal.contracts import DomainError
        actor = Actor(self.user.pk,self.workspace.pk)
        agent, runtime = self.fixture()
        for value in (True, '1', 0, None, -1, 2**63):
            with self.assertRaises(DomainError): core.bind(actor,value,runtime,1)
            with self.assertRaises(DomainError): core.bind(actor,agent,value,1)
            with self.assertRaises(DomainError): core.bind(actor,agent,runtime,value)
        member = Membership.objects.get(user=self.user,workspace=self.workspace)
        member.role='member'; member.save()
        with self.assertRaises(DomainError): core.bind(actor,agent,runtime,1)
        member.role='owner'; member.save()
        other = Workspace.objects.create(name='Other')
        Membership.objects.create(user=self.user,workspace=other,role='owner')
        with self.assertRaises(DomainError) as error: core.bind(Actor(self.user.pk,other.pk),agent,runtime,1)
        self.assertEqual(error.exception.status,404)
        core.bind(actor,agent,runtime,1)
        core.revoke(actor,runtime,1)
        self.assertFalse(core.unbind(actor,agent,2)['enabled'])
        with self.assertRaises(DomainError): core.unbind(actor,agent,3)

from django.test import TransactionTestCase

class BindingConcurrencyTests(TransactionTestCase):
    setUp = fixtures.RuntimeHTTPTests.setUp
    post = fixtures.RuntimeHTTPTests.post
    paired = fixtures.RuntimeHTTPTests.paired
    execute = fixtures.RuntimeHTTPTests.execute
    fixture = RuntimeBindingTests.fixture

    def test_file_connections_revision_and_key(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections, connection
        from workpal.contracts import DomainError
        from workpal.agents.models import RuntimeBinding
        from workpal.audit.models import AuditEvent, Outbox
        self.assertNotIn('memory',connection.settings_dict['NAME'])
        agent, runtime = self.fixture()
        def race(keys, revision):
            barrier = Barrier(2)
            def request(key):
                connections.close_all(); barrier.wait()
                try:
                    return self.execute('runtime.bind',dict(agent_id=agent,runtime_id=runtime),revision,key).data
                except DomainError as error: return error.code
                finally: connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool: return list(pool.map(request,keys))
        results = race(['a','b'],1)
        self.assertEqual(sum(isinstance(x,dict) for x in results),1)
        self.assertIn('revision_conflict',results)
        results = race(['same','same'],2)
        self.assertEqual(results[0],results[1])
        self.assertEqual(RuntimeBinding.objects.get().revision,2)
        self.assertEqual(AuditEvent.objects.filter(action_id='runtime.bind').count(),2)
        self.assertEqual(Outbox.objects.filter(action_id='runtime.bind').count(),2)
