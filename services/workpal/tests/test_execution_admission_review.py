from django.test import TransactionTestCase
from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.execution import service as runs
from workpal.execution.models import Run
from workpal.agents import service as agents
from workpal.work import service as projects, issues, resources
from workpal.contracts import DomainError

class AdmissionReview(AccessFixtures, TransactionTestCase):
    act = WorkpalCase.act
    def setUp(self):
        super().setUp()
        self.member.role='owner'; self.member.save()
        self.project=projects.create(self.actor,'Project')
        self.issue=issues.create(self.actor,self.project['id'],'Task')
        self.agent=agents.create(self.actor,'Builder')
        self.payload=dict(subject={'type':'issue','id':self.issue['id']},agent_id=self.agent['id'],key='intent')
    def test_terminal_and_blocking_states(self):
        for status in ('awaiting_input','completed','failed','cancelled','cancel_requested','recovery_required'):
            Run.objects.all().delete()
            first=runs.start(self.actor,**self.payload)
            Run.objects.filter(pk=first['id']).update(status=status)
            second=runs.start(self.actor,**{**self.payload,'key':status})
            self.assertEqual(first['id']==second['id'],status in ('cancel_requested','recovery_required'),status)
    def test_registry_cached_resource_write_revocation(self):
        grant=self.grant(self.a,read=True,write=True)
        resources.create(self.actor,self.project['id'],'Repo','github','org/repo',source_refs=[{'kind':self.a.kind,'id':self.a.id}])
        self.act(self.actor,'run.start',self.payload,key='cached')
        grant.write=False; grant.save()
        for key in ('cached','new'):
            with self.assertRaises(DomainError) as error:
                self.act(self.actor,'run.start',self.payload,key=key)
            self.assertEqual(error.exception.status,403)
