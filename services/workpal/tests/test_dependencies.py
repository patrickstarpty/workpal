from tests.support import WorkpalCase
from tests.access_support import AccessFixtures
from workpal.contracts import DomainError

class Dependencies(AccessFixtures, WorkpalCase):
    def test_cycle_replay_and_retained_source(self):
        from workpal.work import issues
        self.member.role='owner'; self.member.save()
        p=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        a=issues.create(self.actor,p['id'],'A'); b=issues.create(self.actor,p['id'],'B')
        payload=dict(issue_id=a['id'],depends_on_id=b['id'])
        first=self.act(self.actor,'issue.dependency.add',payload,key='add',revision=1)
        self.assertEqual(first,self.act(self.actor,'issue.dependency.add',payload,key='add',revision=1))
        with self.assertRaises(DomainError): self.act(self.actor,'issue.dependency.add',dict(issue_id=b['id'],depends_on_id=a['id']),key='cycle',revision=1)
        self.act(self.actor,'issue.dependency.remove',payload,key='remove',revision=2)
        with self.assertRaises(DomainError): self.act(self.actor,'issue.dependency.add',dict(issue_id=b['id'],depends_on_id=a['id']),key='historical-cycle',revision=1)
        self.assertEqual(issues.read(self.actor,b['id'])['revision'],1)
        self.assertEqual(self.act(self.actor,'issue.dependency.list',{'issue_id':a['id']}).data['items'],[])
