from tests.support import WorkpalCase
from tests.access_support import AccessFixtures

class WorkflowVersions(AccessFixtures, WorkpalCase):
    def test_create(self):
        self.member.role = 'owner'
        self.member.save()
        result = self.act(self.actor, 'workflow.create', {'name': 'Flow'}, key='create')
        self.assertEqual(result.data['name'], 'Flow')

    def create(self):
        self.member.role='owner'; self.member.save()
        return self.act(self.actor,'workflow.create',{'name':'Original'},key='c').data

    def test_immutable_versions_and_replay(self):
        draft=self.create()
        payload={'draft_id':draft['id']}
        first=self.act(self.actor,'workflow.publish',payload,key='p',revision=1).data
        self.assertEqual(self.act(self.actor,'workflow.publish',payload,key='p',revision=1).data,first)
        self.act(self.actor,'workflow.update',dict(payload,name='Changed'),key='u',revision=2)
        second=self.act(self.actor,'workflow.publish',payload,key='p2',revision=3).data
        self.assertEqual(second['number'],2)
        self.assertNotEqual(first['sha256'],second['sha256'])
        self.assertEqual(self.act(self.actor,'workflow.version.read',{'version_id':first['id']}).data,first)
        self.assertEqual(second['definition'],draft['definition'])

    def test_strict_definition(self):
        from copy import deepcopy
        from workpal.workflows.contracts import default_definition
        from workpal.contracts import DomainError
        self.create()
        for mutate in (lambda d:d.update(code='evil'),lambda d:d['states'].append(d['states'][0]),lambda d:d['transitions'].append({'from':'missing','to':'done'}),lambda d:d['transitions'].append(d['transitions'][0]),lambda d:d['review_policy'].update(reviewer_roles=['owner','owner'])):
            definition=deepcopy(default_definition()); mutate(definition)
            with self.assertRaises(DomainError):
                self.act(self.actor,'workflow.create',{'name':'Bad','definition':definition},key='bad')
        a=default_definition(); a['states'].clear()
        self.assertEqual(len(default_definition()['states']),7)

    def test_failed_publish_atomic(self):
        from workpal.workflows.models import WorkflowVersion
        from workpal.audit.models import Outbox
        from workpal.contracts import DomainError
        draft=self.create(); before=Outbox.objects.count()
        with self.assertRaises(DomainError):
            self.act(self.actor,'workflow.publish',{'draft_id':draft['id']},key='bad',revision=2)
        self.assertEqual(WorkflowVersion.objects.count(),0)
        self.assertEqual(Outbox.objects.count(),before)
