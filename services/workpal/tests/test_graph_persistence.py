from django.test import TestCase
from django.contrib.auth import get_user_model
from workpal.identity.models import Membership, Workspace
from workpal.contracts import Actor, ActionRequest
from workpal.actions.registry import execute
from workpal.workflows.graph import compile_graph


class GraphPersistenceTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create(username='graph-owner')
        workspace = Workspace.objects.create(name='Graph review')
        Membership.objects.create(user=user, workspace=workspace, role='owner')
        self.actor = Actor(user.pk, workspace.pk)
        self.definition = dict(nodes=[dict(id='start', type='start', config={}),
            dict(id='end', type='end', config={})], edges=[dict(
                **{'from': 'start', 'to': 'end'}, on='always', required=True, max_traversals=0)],
            declared_fields=[])

    def test_registered_graph_create_and_authorized_read(self):
        result = execute(self.actor, ActionRequest('workflow_graph.create',
            dict(name='Release graph', definition=self.definition), None, 'graph-create'))
        self.assertEqual(result.state, 'completed')
        self.assertEqual(result.data['name'], 'Release graph')
        self.assertEqual(result.data['revision'], 1)
        self.assertEqual(result.data['current_version_id'], 0)
        self.assertEqual(result.data['definition'], compile_graph(self.definition)['definition'])
        read = execute(self.actor, ActionRequest('workflow_graph.read',
            dict(draft_id=result.data['id']), None, None))
        self.assertEqual(read.data, result.data)

    def test_hash_and_detached_views(self):
        from workpal.workflows import persistence as p
        draft=p.create(self.actor,'One',self.definition)
        version=p.publish(self.actor,draft['id'],1)
        draft['definition']['nodes'].clear()
        changed=p.update(self.actor,draft['id'],2,'Two',self.definition)
        second=p.publish(self.actor,draft['id'],changed['revision'])
        self.assertEqual(version['graph']['sha256'],second['graph']['sha256'])
        self.assertEqual(p.read_version(self.actor,version['id'])['name'],'One')

    def test_cas_and_key_conflict(self):
        from workpal.workflows import persistence as p
        from workpal.contracts import DomainError
        request=ActionRequest('workflow_graph.create',dict(name='One',definition=self.definition),None,'same')
        draft=execute(self.actor,request).data
        self.assertEqual(execute(self.actor,request).data,draft)
        with self.assertRaises(DomainError) as error:
            execute(self.actor,ActionRequest('workflow_graph.create',dict(name='Other',definition=self.definition),None,'same'))
        self.assertEqual(error.exception.status,409)
        p.publish(self.actor,draft['id'],1)
        with self.assertRaises(DomainError) as error: p.publish(self.actor,draft['id'],1)
        self.assertEqual(error.exception.code,'revision_conflict')

    def test_authorized_pagination(self):
        from workpal.workflows import persistence as p
        ids=[p.create(self.actor,str(i),self.definition)['id'] for i in range(3)]
        page=p.list_drafts(self.actor,limit=2)
        self.assertEqual([x['id'] for x in page['items']],ids[:2])
        self.assertNotIn('definition',page['items'][0])
        last=p.list_drafts(self.actor,cursor=page['next_cursor'],limit=2)
        self.assertEqual([x['id'] for x in last['items']],ids[2:])
        self.assertEqual(last['next_cursor'],0)

    def test_legacy_workflow_unchanged(self):
        from workpal.workflows import service, persistence as p
        old=service.create(self.actor,'Legacy')
        published=service.publish(self.actor,old['id'],1)
        draft=p.create(self.actor,'Graph',self.definition)
        p.publish(self.actor,draft['id'],1)
        self.assertEqual(service.read_version(self.actor,published['id']),published)

    def test_audit_write_failure_rollback(self):
        from unittest.mock import patch
        from workpal.actions import registry
        from workpal.workflows.graph_models import GraphDraft
        from workpal.access.models import RegisteredObject, SourceLink
        from workpal.actions.models import IdempotencyResult
        from workpal.workflows.graph_models import GraphVersion
        from workpal.audit.models import AuditEvent, Outbox
        models=[GraphDraft,GraphVersion,RegisteredObject,SourceLink,IdempotencyResult,AuditEvent,Outbox]
        draft=execute(self.actor,ActionRequest('workflow_graph.create',dict(name='Draft',definition=self.definition),None,'draft')).data
        before=[m.objects.count() for m in models]
        revision=draft['revision']
        original=registry.record
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise RuntimeError('after audit')
        request=ActionRequest('workflow_graph.publish',dict(draft_id=draft['id']),revision,'retry')
        with patch.object(registry,'record',side_effect=fail):
            with self.assertRaises(RuntimeError): execute(self.actor,request)
        self.assertEqual([m.objects.count() for m in models],before)
        row=GraphDraft.objects.get(pk=draft['id'])
        self.assertEqual(row.revision,revision)
        self.assertIsNone(row.current_version_id)
        self.assertEqual(execute(self.actor,request).state,'completed')

    def sourced(self):
        import copy
        from workpal.agents import service as agents
        from workpal.access.service import register_object, resolve
        from workpal.access.models import SourceGrant
        from workpal.contracts import ObjectRef
        agent=agents.create(self.actor,'Agent')
        source=ObjectRef('document','input')
        register_object(self.actor.workspace_id,source,is_source=True)
        grant=SourceGrant.objects.create(user_id=self.actor.user_id,source=resolve(source),read=True,write=True,publish=True)
        definition=copy.deepcopy(self.definition)
        definition['nodes'].append(dict(id='task',type='agent_task',config=dict(agent_id=agent['id'],input_refs=['document:input'])))
        definition['edges']=[dict(**{'from':a,'to':b},on='always',required=True,max_traversals=0) for a,b in [('start','task'),('task','end')]]
        return definition,grant

    def test_reference_resolution_matrix(self):
        from workpal.workflows import persistence as p
        from workpal.contracts import DomainError
        definition,_=self.sourced()
        for value,code in [('bad','invalid_input'),('document:a:b','invalid_input'),('document:','invalid_input'),('Document:a','invalid_input'),('document:missing','permission_denied')]:
            definition['nodes'][-1]['config']['input_refs']=[value]
            with self.subTest(value=value), self.assertRaises(DomainError) as error:
                p.create(self.actor,'One',definition)
            self.assertEqual(error.exception.code,code)

    def test_publish_current_agent_and_input_access(self):
        from workpal.workflows import persistence as p
        from workpal.contracts import DomainError
        definition,grant=self.sourced()
        grant.publish=False; grant.save()
        draft=p.create(self.actor,'One',definition)
        self.assertEqual(p.read(self.actor,draft['id']),draft)
        with self.assertRaises(DomainError) as error: p.publish(self.actor,draft['id'],1)
        self.assertEqual(error.exception.status,403)

    def test_draft_sources_accumulate(self):
        from workpal.workflows import persistence as p
        from workpal.contracts import DomainError
        definition,grant=self.sourced()
        draft=p.create(self.actor,'One',definition)
        p.update(self.actor,draft['id'],1,'Two',self.definition)
        grant.read=False; grant.save()
        with self.assertRaises(DomainError): p.read(self.actor,draft['id'])

    def test_publish_replay_revocation(self):
        from workpal.workflows import persistence as p
        from workpal.contracts import DomainError
        definition,grant=self.sourced()
        draft=p.create(self.actor,'One',definition)
        request=ActionRequest('workflow_graph.publish',dict(draft_id=draft['id']),1,'publish')
        version=execute(self.actor,request).data
        grant.publish=False; grant.save()
        self.assertEqual(p.read_version(self.actor,version['id']),version)
        with self.assertRaises(DomainError) as error: execute(self.actor,request)
        self.assertEqual(error.exception.status,403)


from django.test import TransactionTestCase

class GraphPublishConcurrencyTests(TransactionTestCase):
    def test_two_connection_publish(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from workpal.workflows import persistence as p
        from workpal.workflows.graph_models import GraphVersion
        from workpal.contracts import DomainError
        user=get_user_model().objects.create(username='concurrent-owner')
        workspace=Workspace.objects.create(name='Concurrent')
        Membership.objects.create(user=user,workspace=workspace,role='owner')
        actor=Actor(user.pk,workspace.pk)
        definition=dict(nodes=[dict(id='start',type='start',config={}),dict(id='end',type='end',config={})],edges=[dict(**{'from':'start','to':'end'},on='always',required=True,max_traversals=0)],declared_fields=[])
        draft=p.create(actor,'Concurrent',definition)
        barrier=Barrier(2)
        def publish():
            connections.close_all()
            try:
                connections['default'].ensure_connection()
                barrier.wait(timeout=10)
                try: return ('ok',p.publish(actor,draft['id'],1)['id'])
                except DomainError as error: return (error.code,error.status)
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:publish(),range(2)))
        self.assertEqual(sum(code=='ok' for code,_ in results),1,results)
        for code,status in results:
            self.assertIn(code,('ok','storage_busy','revision_conflict'))
            if code=='storage_busy':
                with self.assertRaises(DomainError) as error: p.publish(actor,draft['id'],1)
                self.assertEqual(error.exception.code,'revision_conflict')
        self.assertEqual(GraphVersion.objects.filter(draft_id=draft['id']).count(),1)
        self.assertEqual(p.read(actor,draft['id'])['current_version_id'],GraphVersion.objects.get(draft_id=draft['id']).pk)
