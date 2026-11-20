from tests.support import WorkpalCase
from tests.access_support import AccessFixtures

class AgentConfiguration(AccessFixtures, WorkpalCase):
    def test_registry_create(self):
        self.member.role='owner'; self.member.save()
        result=self.act(self.actor,'agent.create',{'name':'Builder'},key='agent')
        self.assertEqual(result.data['provider_key'],'copilot_cli')
    def test_management_and_revision(self):
        from workpal.agents import service
        from workpal.contracts import DomainError
        self.member.role='owner'; self.member.save()
        a=service.create(self.actor,'Builder',model='chosen')
        self.assertEqual(service.update(self.actor,a['id'],1,model='next')['model'],'next')
        with self.assertRaises(DomainError): service.update(self.actor,a['id'],1,name='stale')
        self.member.role='member'; self.member.save()
        self.assertEqual(service.read(self.actor,a['id'])['model'],'next')
        with self.assertRaises(DomainError): service.create(self.actor,'Forbidden')
    def test_invalid_provider_and_fields(self):
        from workpal.agents import service
        from workpal.contracts import DomainError
        self.member.role='owner'; self.member.save()
        for name,provider in [('', 'copilot_cli'),('x','unknown')]:
            with self.assertRaises(DomainError): service.create(self.actor,name,provider)
