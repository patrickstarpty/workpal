from tests.support import WorkpalCase
from tests.access_support import AccessFixtures

class ProjectWorkflows(AccessFixtures, WorkpalCase):
    def test_builtin(self):
        from workpal.workflows.models import WorkflowVersion
        from workpal.audit.models import Outbox
        self.member.role='owner'
        self.member.save()
        p=self.act(self.actor,'project.create',{'name':'P'},key='p').data
        before=Outbox.objects.count()
        result=self.act(self.actor,'project.workflow.read',{'project_id':p['id']})
        self.assertEqual(result.data['origin'],'builtin')
        self.assertEqual(result.data['version_id'],0)
        self.assertEqual(WorkflowVersion.objects.count(),0)
        self.assertEqual(Outbox.objects.count(),before)

    def setup_project(self):
        self.member.role='owner'
        self.member.save()
        return self.act(self.actor,'project.create',{'name':'P'},key='p').data

    def version(self):
        from workpal.workflows import service
        d=service.create(self.actor,'Flow')
        return d, service.publish(self.actor,d['id'],d['revision'])

    def bind(self,p,v,key='bind'):
        payload=dict(project_id=p['id'],workflow_version_id=v)
        waiting=self.act(self.actor,'project.set_workflow',payload,key=key,revision=p['revision'])
        self.assertEqual(waiting.state,'waiting_confirmation')
        from workpal.work import service
        self.assertEqual(service.read(self.actor,p['id'])['revision'],p['revision'])
        return self.act(self.actor,'project.set_workflow',payload,key=key,revision=p['revision'],
                        confirmation_id=waiting.data['confirmation_id'])

    def test_binding_versions_and_replay(self):
        from workpal.work import service
        from workpal.workflows import service as workflows
        from workpal.audit.models import Outbox
        p=self.setup_project()
        d,v=self.version()
        bound=self.bind(p,v['id'])
        self.assertEqual(bound.data['workflow_version_id'],v['id'])
        self.assertEqual(bound.data['revision'],2)
        count=Outbox.objects.count()
        replay=self.act(self.actor,'project.set_workflow',dict(project_id=p['id'],workflow_version_id=v['id']),key='bind',revision=1)
        self.assertEqual(replay.data,bound.data)
        self.assertEqual(Outbox.objects.count(),count)
        old=service.snapshot_workflow(self.actor,p['id'])
        d=workflows.update(self.actor,d['id'],2,name='Flow 2')
        v2=workflows.publish(self.actor,d['id'],d['revision'])
        self.assertEqual(service.snapshot_workflow(self.actor,p['id']),old)
        self.bind(bound.data,v2['id'],'v2')
        self.assertEqual(service.snapshot_workflow(self.actor,p['id'])['name'],'Flow 2')
        self.assertEqual(old['name'],'Flow')
        self.assertEqual(workflows.read_version(self.actor,v['id'])['name'],'Flow')
        old['definition']['states'].clear()
        current=service.snapshot_workflow(self.actor,p['id'])
        current['definition']['states'].clear()
        self.assertEqual(len(service.snapshot_workflow(self.actor,p['id'])['definition']['states']),7)

    def test_invalid_writes_and_member(self):
        from workpal.work import service
        from workpal.contracts import DomainError
        p=self.setup_project()
        _,v=self.version()
        for changes in ({'workflow_version_id':v['id']},{'workflow_version':v['id']}):
            with self.assertRaises(DomainError):
                service.update(self.actor,p['id'],1,**changes)
        with self.assertRaises(DomainError):
            service.set_workflow(self.actor,p['id'],v['id'],2)
        with self.assertRaises(DomainError):
            service.set_workflow(self.actor,p['id'],999999,1)
        self.member.role='member'
        self.member.save()
        self.act(self.actor,'project.workflow.read',{'project_id':p['id']})
        with self.assertRaises(DomainError):
            service.set_workflow(self.actor,p['id'],v['id'],1)

    def test_historical_sources_and_revocation(self):
        from workpal.access.service import register_object
        from workpal.access.models import SourceGrant, RegisteredObject
        from workpal.contracts import ObjectRef, DomainError
        from workpal.work import service
        from workpal.workflows import service as workflows
        p=self.setup_project()
        _,v=self.version()
        source=ObjectRef('document','restricted-workflow')
        register_object(self.actor.workspace_id,source,is_source=True)
        obj=RegisteredObject.objects.get(kind=source.kind,object_id=source.id)
        grant=SourceGrant.objects.create(source=obj,user=self.user,read=True,write=False,publish=False)
        register_object(self.actor.workspace_id,workflows.ref(v['id'],True),[source])
        with self.assertRaises(DomainError):
            service.set_workflow(self.actor,p['id'],v['id'],1)
        grant.write=True
        grant.save()
        bound=self.bind(p,v['id'])
        cleared=self.bind(bound.data,0,'clear')
        self.assertEqual(cleared.data['workflow_version_id'],0)
        grant.read=False
        grant.save()
        for operation in (
            lambda:service.read(self.actor,p['id']),
            lambda:service.snapshot_workflow(self.actor,p['id']),
            lambda:self.act(self.actor,'project.set_workflow',dict(project_id=p['id'],workflow_version_id=v['id']),key='bind',revision=1)):
            with self.assertRaises(DomainError):
                operation()

    def test_builtin_copy_and_existing_dto(self):
        from workpal.work import service
        p=self.setup_project()
        self.assertEqual(p['workflow_version_id'],0)
        self.assertEqual(service.list_projects(self.actor)['items'][0],p)
        first=service.snapshot_workflow(self.actor,p['id'])
        first['definition']['states'].clear()
        second=service.snapshot_workflow(self.actor,p['id'])
        self.assertEqual(len(second['definition']['states']),7)
        self.assertEqual(first['sha256'],second['sha256'])
