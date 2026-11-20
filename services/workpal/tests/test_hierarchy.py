from tests.support import WorkpalCase
from tests.access_support import AccessFixtures

class Hierarchy(AccessFixtures, WorkpalCase):
    def test_registry_set_parent(self):
        self.member.role='owner'; self.member.save()
        p=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        a=self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'a'},key='a').data
        b=self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'b'},key='b').data
        result=self.act(self.actor,'issue.set_parent',{'issue_id':b['id'],'parent_issue_id':a['id']},key='s',revision=1).data
        self.assertEqual(result['parent_issue_id'],a['id'])

    def setup_pair(self):
        self.member.role='owner'; self.member.save()
        self.p=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        self.a=self.act(self.actor,'issue.create',{'project_id':self.p['id'],'title':'a'},key='a').data
        self.b=self.act(self.actor,'issue.create',{'project_id':self.p['id'],'title':'b'},key='b').data

    def change(self,parent,key='s',revision=1):
        return self.act(self.actor,'issue.set_parent',{'issue_id':self.b['id'],'parent_issue_id':parent},key=key,revision=revision).data

    def test_roots(self):
        self.setup_pair(); self.assertEqual(self.a['parent_issue_id'],0)

    def test_create_child(self):
        self.setup_pair()
        c=self.act(self.actor,'issue.create',{'project_id':self.p['id'],'title':'c','parent_issue_id':self.a['id']},key='c').data
        self.assertEqual(c['parent_issue_id'],self.a['id'])
        self.assertNotEqual(c['requirements_version_id'],self.a['requirements_version_id'])
        self.assertEqual(c['workflow_snapshot'],self.a['workflow_snapshot'])

    def test_detach(self):
        self.setup_pair(); self.change(self.a['id'])
        self.assertEqual(self.change(0,'detach',2)['parent_issue_id'],0)

    def test_parent_revision_independent(self):
        self.setup_pair(); self.change(self.a['id'])
        self.assertEqual(self.act(self.actor,'issue.read',{'issue_id':self.a['id']}).data,self.a)

    def test_replay(self):
        self.setup_pair(); first=self.change(self.a['id'])
        self.assertEqual(first,self.change(self.a['id']))

    def test_self_rejected(self):
        from workpal.contracts import DomainError
        self.setup_pair()
        with self.assertRaises(DomainError): self.change(self.b['id'])

    def test_cycle_rejected(self):
        from workpal.contracts import DomainError
        self.setup_pair(); self.change(self.a['id'])
        with self.assertRaises(DomainError):
            self.act(self.actor,'issue.set_parent',{'issue_id':self.a['id'],'parent_issue_id':self.b['id']},key='cycle',revision=1)

    def test_stale(self):
        from workpal.contracts import DomainError
        self.setup_pair()
        with self.assertRaises(DomainError) as caught: self.change(self.a['id'],revision=2)
        self.assertEqual(caught.exception.status,409)

    def test_parent_filter(self):
        self.setup_pair(); self.change(self.a['id'])
        roots=self.act(self.actor,'issue.list',{'parent_issue_id':0}).data
        children=self.act(self.actor,'issue.children.list',{'issue_id':self.a['id']}).data
        self.assertEqual([i['id'] for i in roots['items']],[self.a['id']])
        self.assertEqual([i['id'] for i in children['items']],[self.b['id']])

    def test_update_rejected(self):
        from workpal.contracts import DomainError
        self.setup_pair()
        with self.assertRaises(DomainError):
            self.act(self.actor,'issue.update',{'issue_id':self.b['id'],'parent_issue_id':self.a['id']},key='u',revision=1)
