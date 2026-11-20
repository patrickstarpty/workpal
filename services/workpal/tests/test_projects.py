from tests.support import WorkpalCase
from tests.access_support import AccessFixtures

class Projects(AccessFixtures, WorkpalCase):
    def test_create(self):
        self.member.role = 'owner'
        self.member.save()
        result = self.act(self.actor, 'project.create', {'name': 'one'}, key='create')
        self.assertEqual(result.data['name'], 'one')

    def owner(self):
        self.member.role = 'owner'
        self.member.save()

    def create(self, key='p', name='same'):
        self.owner()
        return self.act(self.actor, 'project.create', {'name': name}, key=key).data

    def reject(self, status, action, payload, **kw):
        from workpal.contracts import DomainError
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, action, payload, **kw)
        self.assertEqual(caught.exception.status, status)

    def test_replay_update_cas_and_events(self):
        from workpal.audit.models import Outbox
        p = self.create()
        self.assertEqual(self.create(), p)
        payload = dict(project_id=p['id'], name='<img>', description=' raw ')
        updated = self.act(self.actor, 'project.update', payload, key='u', revision=1).data
        self.assertEqual(updated['revision'], 2)
        self.assertEqual(updated['description'], ' raw ')
        self.assertEqual(self.act(self.actor, 'project.update', payload, key='u', revision=1).data, updated)
        self.reject(409, 'project.update', payload, key='stale', revision=1)
        self.assertEqual(list(Outbox.objects.values_list('action_id', flat=True)), ['project.create','project.update'])

    def test_same_name_explicit_selection(self):
        a, b = self.create('a'), self.create('b')
        self.assertNotEqual(a['id'], b['id'])
        for p in (a,b):
            self.assertEqual(self.act(self.actor,'project.read',{'project_id':p['id']}).data, p)
        self.reject(400,'project.read',{'name':'same'})

    def test_workspace_isolation(self):
        from workpal.contracts import Actor
        from workpal.identity.models import Membership
        p = self.create()
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        actor = Actor(self.user.pk,self.other.pk)
        from workpal.contracts import DomainError
        with self.assertRaises(DomainError):
            self.act(actor,'project.read',{'project_id':p['id']})
        self.assertEqual(self.act(actor,'project.list',{'cursor':p['id']}).data, {'items':[],'next_cursor':0})

    def test_member_management_forbidden(self):
        p = self.create()
        self.member.role='member'
        self.member.save()
        self.act(self.actor,'project.read',{'project_id':p['id']})
        for action,payload in [('create',{'name':'x'}),('update',{'project_id':p['id'],'name':'x'}),('archive',{'project_id':p['id']}),('restore',{'project_id':p['id']})]:
            self.reject(403,'project.'+action,payload,key=action,revision=1)

    def test_archive_restore(self):
        from workpal.audit.models import Outbox
        p=self.create()
        payload={'project_id':p['id']}
        self.act(self.actor,'project.archive',payload,key='a',revision=1)
        self.assertEqual(self.act(self.actor,'project.list',{}).data['items'],[])
        self.assertTrue(self.act(self.actor,'project.read',payload).data['archived'])
        self.assertEqual(len(self.act(self.actor,'project.list',{'include_archived':True}).data['items']),1)
        self.act(self.actor,'project.restore',payload,key='r',revision=2)
        self.assertEqual(len(self.act(self.actor,'project.list',{}).data['items']),1)
        self.assertEqual(list(Outbox.objects.values_list('action_id',flat=True)),['project.create','project.archive','project.restore'])

    def test_strict_fields(self):
        self.owner()
        for payload in ({}, {'name':''},{'name':3},{'name':'x'*201},{'name':'x','description':'x'*10001},{'name':'x','sources':[]}):
            self.reject(400,'project.create',payload,key='bad')
        for payload in ({'limit':0},{'limit':201},{'limit':True},{'cursor':-1},{'cursor':'1'},{'include_archived':1},{'query':None},{'extra':1}):
            self.reject(400,'project.list',payload)

    def test_visible_pagination_and_revocation(self):
        from workpal.contracts import ObjectRef
        hidden=self.create('h')
        first=self.create('first')
        last=self.create('last')
        self.register(self.workspace.pk,ObjectRef('project',str(hidden['id'])),[self.a])
        page=self.act(self.actor,'project.list',{'limit':1}).data
        self.assertEqual(page,{'items':[first],'next_cursor':first['id']})
        self.assertEqual(self.act(self.actor,'project.list',{'limit':1,'cursor':page['next_cursor']}).data,{'items':[last],'next_cursor':0})
        grant=self.grant(self.a,read=True,write=True)
        payload={'project_id':hidden['id'],'name':'changed'}
        self.act(self.actor,'project.update',payload,key='u',revision=1)
        grant.read=False
        grant.save()
        self.reject(403,'project.read',{'project_id':hidden['id']})
        self.reject(403,'project.update',payload,key='u',revision=1)
        self.reject(403,'project.create',{'name':'same'},key='h')
        self.assertEqual(len(self.act(self.actor,'project.list',{}).data['items']),2)

    def test_read_write_grants_distinct(self):
        from workpal.contracts import ObjectRef
        p=self.create()
        self.register(self.workspace.pk,ObjectRef('project',str(p['id'])),[self.a])
        grant=self.grant(self.a,read=True,write=False)
        self.act(self.actor,'project.read',{'project_id':p['id']})
        self.reject(403,'project.update',{'project_id':p['id'],'name':'x'},key='u',revision=1)
        grant.read=False
        grant.write=True
        grant.save()
        self.reject(403,'project.read',{'project_id':p['id']})
