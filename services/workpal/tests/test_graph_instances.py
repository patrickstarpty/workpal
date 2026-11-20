from django.test import TestCase
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership
from workpal.contracts import Actor, ActionRequest
from workpal.actions.registry import execute
from workpal.work import service, issues
from workpal.agents import service as agents
from workpal.workflows import persistence

class GraphInstanceTests(TestCase):
    def setUp(self):
        u=get_user_model().objects.create(username='instance-owner')
        w=Workspace.objects.create(name='Instances')
        Membership.objects.create(user=u,workspace=w,role='owner')
        self.actor=Actor(u.pk,w.pk)
        self.agent=agents.create(self.actor,'Agent')
        project=service.create(self.actor,'Project')
        self.issue=issues.create(self.actor,project['id'],'Issue')
        definition=dict(nodes=[dict(id='s',type='start',config={}),dict(id='t',type='agent_task',config=dict(agent_id=self.agent['id'],input_refs=[])),dict(id='e',type='end',config={})],edges=[dict(**{'from':a,'to':b},on='always',required=True,max_traversals=0) for a,b in [('s','t'),('t','e')]],declared_fields=[])
        d=persistence.create(self.actor,'Graph',definition)
        self.version=persistence.publish(self.actor,d['id'],1)
    def initialize(self,key='initialize'):
        return execute(self.actor,ActionRequest('workflow_graph.instance.initialize',dict(subject=dict(type='issue',id=str(self.issue['id'])),version_id=self.version['id']),None,key)).data
    def test_initialize_read(self):
        data=self.initialize()
        self.assertEqual(data['state'],'initialized')
        self.assertEqual(execute(self.actor,ActionRequest('workflow_graph.instance.read',dict(instance_id=data['id']),None,None)).data,data)
    def test_hash_detachment_and_foreign_keys(self):
        import hashlib,json
        from workpal.workflows import instances
        from workpal.workflows.graph_models import GraphInstance
        from workpal.execution.models import Run
        before=Run.objects.count()
        data=self.initialize()
        row=GraphInstance.objects.get(pk=data['id'])
        self.assertEqual((row.issue_id,row.requirements_id,row.version_id),(self.issue['id'],self.issue['requirements_version_id'],self.version['id']))
        self.assertEqual(data['sha256'],hashlib.sha256(json.dumps(data['snapshot'],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())
        data['snapshot']['agents'].clear()
        self.assertEqual(len(instances.read(self.actor,row.pk)['snapshot']['agents']),1)
        self.assertEqual(Run.objects.count(),before)
        self.assertEqual(issues.read(self.actor,self.issue['id']),self.issue)
    def test_replay_and_independent_keys(self):
        from workpal.workflows.graph_models import GraphInstance
        from workpal.contracts import DomainError
        data=self.initialize()
        self.assertEqual(self.initialize(),data)
        self.assertNotEqual(self.initialize('other')['id'],data['id'])
        with self.assertRaises(DomainError) as error:
            execute(self.actor,ActionRequest('workflow_graph.instance.initialize',dict(subject=dict(type='issue',id=str(self.issue['id'])),version_id=self.version['id']+1),None,'initialize'))
        # Resolution precedes cache lookup, so use another existing subject for conflict.
        other=issues.create(self.actor,self.issue['project_id'],'Other')
        with self.assertRaises(DomainError) as error:
            execute(self.actor,ActionRequest('workflow_graph.instance.initialize',dict(subject=dict(type='issue',id=str(other['id'])),version_id=self.version['id']),None,'initialize'))
        self.assertEqual(error.exception.status,409)
        self.assertEqual(GraphInstance.objects.count(),2)
    def test_requirements_history_and_today_revocation(self):
        from workpal.access import service as access
        from workpal.access.models import SourceGrant
        from workpal.contracts import ObjectRef,DomainError
        from workpal.workflows import instances
        data=self.initialize()
        changed=issues.update(self.actor,self.issue['id'],self.issue['revision'],title='New title')
        source=ObjectRef('document','today')
        access.register_object(self.actor.workspace_id,source,is_source=True)
        grant=SourceGrant.objects.create(user_id=self.actor.user_id,source=access.resolve(source),read=True,write=True,publish=True)
        access.register_object(self.actor.workspace_id,issues.requirement_ref(changed['requirements_version_id']),[source])
        grant.read=False; grant.save()
        self.assertEqual(self.initialize(),data)
        with self.assertRaises(DomainError): self.initialize('new')
        self.assertEqual(instances.read(self.actor,data['id']),data)
        grant.read=True; grant.save()
        new=self.initialize('new')
        self.assertEqual(new['snapshot']['requirements']['title'],'New title')
        self.assertEqual(self.initialize(),data)
    def test_admission_failure_preserves_history(self):
        from unittest.mock import patch
        from workpal.contracts import DomainError
        from workpal.workflows import instances
        data=self.initialize()
        with patch('workpal.workflows.instances.admit_initialization',side_effect=DomainError('capability_unavailable','Unavailable',status=409)):
            with self.assertRaises(DomainError): self.initialize()
            self.assertEqual(instances.read(self.actor,data['id']),data)
    def test_audit_failure_rolls_back(self):
        from unittest.mock import patch
        from workpal.actions import registry
        from workpal.workflows.graph_models import GraphInstance
        from workpal.access.models import RegisteredObject,SourceLink
        from workpal.actions.models import IdempotencyResult
        from workpal.audit.models import AuditEvent,Outbox
        from workpal.contracts import DomainError
        models=[GraphInstance,RegisteredObject,SourceLink,IdempotencyResult,AuditEvent,Outbox]
        before=[m.objects.count() for m in models]
        original=registry.record
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise DomainError('storage_busy','Retry',status=503)
        with patch.object(registry,'record',side_effect=fail):
            with self.assertRaises(DomainError): self.initialize()
        self.assertEqual([m.objects.count() for m in models],before)
        self.assertEqual(self.initialize(),self.initialize())
    def test_subject_write_and_saved_source_read(self):
        from workpal.access import service as access
        from workpal.access.models import SourceGrant
        from workpal.contracts import ObjectRef,DomainError
        from workpal.workflows import instances
        source=ObjectRef('document','subject')
        access.register_object(self.actor.workspace_id,source,is_source=True)
        grant=SourceGrant.objects.create(user_id=self.actor.user_id,source=access.resolve(source),read=True,write=True,publish=True)
        access.register_object(self.actor.workspace_id,issues.ref(self.issue['id']),[source])
        data=self.initialize()
        grant.write=False; grant.save()
        for key in ('initialize','new'):
            with self.assertRaises(DomainError): self.initialize(key)
        self.assertEqual(instances.read(self.actor,data['id']),data)
        grant.write=True; grant.read=False; grant.save()
        with self.assertRaises(DomainError): self.initialize()
        with self.assertRaises(DomainError): instances.read(self.actor,data['id'])
    def test_strict_subject(self):
        from workpal.contracts import SubjectRef,DomainError
        from workpal.workflows import instances
        for value in ({'type':'issue','id':'1'},SubjectRef('issue','01'),SubjectRef('issue',' 1'),SubjectRef('issue','+1'),SubjectRef('issue',True)):
            with self.subTest(value=value),self.assertRaises(DomainError): instances.initialize(self.actor,value,self.version['id'],'strict')
