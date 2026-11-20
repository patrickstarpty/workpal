from tests.support import WorkpalCase
from tests.access_support import AccessFixtures

class Resources(AccessFixtures, WorkpalCase):
    def test_create(self):
        self.member.role='owner'; self.member.save()
        p=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        r=self.act(self.actor,'resource.create',dict(project_id=p['id'],label='repo',provider='github',repository_ref='https://github.com/org/repo'),key='r').data
        self.assertEqual(r['verification_status'],'unverified')

    def setup_resource(self, **extra):
        self.member.role='owner'; self.member.save()
        p=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        payload=dict(project_id=p['id'],label='repo',provider='github',repository_ref='org/repo',checkout_ref='main',**extra)
        r=self.act(self.actor,'resource.create',payload,key='r').data
        return payload,r,dict(project_id=p['id'],resource_id=r['id'])

    def test_cas_checkout_and_replay(self):
        from workpal.contracts import DomainError
        payload,r,sel=self.setup_resource()
        self.assertEqual(self.act(self.actor,'resource.create',payload,key='r').data,r)
        updated=self.act(self.actor,'resource.update',dict(sel,label='new'),key='u',revision=1).data
        self.assertEqual(updated['checkout_ref'],'main')
        with self.assertRaises(DomainError): self.act(self.actor,'resource.update',dict(sel,label='stale'),key='s',revision=1)
        cleared=self.act(self.actor,'resource.update',dict(sel,checkout_ref=''),key='c',revision=2).data
        self.assertEqual(cleared['checkout_ref'],'')

    def test_sources_append_and_revocation(self):
        from workpal.contracts import DomainError
        grant=self.grant(self.a,read=True,write=True)
        payload,r,sel=self.setup_resource(source_refs=[dict(kind=self.a.kind,id=self.a.id)])
        self.act(self.actor,'resource.update',dict(sel,source_refs=[]),key='u',revision=1)
        grant.read=False; grant.save()
        for action,body,kw in [('read',sel,{}),('update',dict(sel,label='x'),dict(key='u2',revision=2)),('create',payload,dict(key='r'))]:
            with self.assertRaises(DomainError): self.act(self.actor,'resource.'+action,body,**kw)
        self.assertEqual(self.act(self.actor,'resource.list',{'project_id':sel['project_id']}).data['items'],[])

    def test_remove_confirmation_and_restore(self):
        payload,r,sel=self.setup_resource()
        waiting=self.act(self.actor,'resource.remove',sel,key='d',revision=1)
        self.assertEqual(waiting.state,'waiting_confirmation')
        self.act(self.actor,'resource.remove',sel,key='d',revision=1,confirmation_id=waiting.data['confirmation_id'])
        self.assertEqual(self.act(self.actor,'resource.list',{'project_id':sel['project_id']}).data['items'],[])
        self.assertTrue(self.act(self.actor,'resource.read',sel).data['archived'])
        self.assertFalse(self.act(self.actor,'resource.restore',sel,key='restore',revision=2).data['archived'])

    def test_invalid_inputs_and_identity(self):
        from workpal.contracts import DomainError
        from workpal.work import resources
        payload,r,sel=self.setup_resource()
        for extra in [dict(password='secret'),dict(verification_status='verified'),dict(source_refs='[]'),dict(source_refs=[{'kind':'x','id':'1','extra':1}]),dict(repository_ref='https://u:p@github.com/a'),dict(repository_ref='https://github.com/a?token=x'),dict(repository_ref='a\nb')]:
            with self.assertRaises(DomainError): self.act(self.actor,'resource.create',{**payload,**extra},key='bad')
        with self.assertRaises(DomainError): resources.update(self.actor,**sel,revision=1,workspace_id=self.other.pk)
        other=self.act(self.actor,'project.create',{'name':'other'},key='other').data
        with self.assertRaises(DomainError): self.act(self.actor,'resource.read',dict(sel,project_id=other['id']))

    def test_atomic_failure_and_archived_parent(self):
        from workpal.contracts import DomainError
        from workpal.work import resources
        from workpal.work.models import ProjectResource
        payload,r,sel=self.setup_resource()
        before=ProjectResource.objects.count()
        with self.assertRaises(DomainError): resources.create(self.actor,**{**payload,'source_refs':[{'kind':'absent','id':'1'}]})
        self.assertEqual(ProjectResource.objects.count(),before)
        self.act(self.actor,'project.archive',{'project_id':sel['project_id']},key='archive',revision=1)
        self.act(self.actor,'resource.read',sel)
        with self.assertRaises(DomainError): self.act(self.actor,'resource.create',payload,key='archived')

    def test_visible_pagination_member_and_workspace(self):
        from workpal.contracts import Actor, DomainError
        from workpal.identity.models import Membership
        payload,r,sel=self.setup_resource()
        for i in range(2): self.act(self.actor,'resource.create',payload,key='more'+str(i))
        page=self.act(self.actor,'resource.list',dict(project_id=sel['project_id'],limit=1)).data
        self.assertEqual(page['items'],[r]); self.assertEqual(page['next_cursor'],r['id'])
        self.member.role='member'; self.member.save()
        self.act(self.actor,'resource.read',sel)
        with self.assertRaises(DomainError): self.act(self.actor,'resource.update',dict(sel,label='x'),key='member',revision=1)
        Membership.objects.create(user=self.user,workspace=self.other,role='owner')
        with self.assertRaises(DomainError): self.act(Actor(self.user.pk,self.other.pk),'resource.read',sel)

    def test_multiple_sources_require_all_grants(self):
        from workpal.contracts import DomainError
        payload,r,sel=self.setup_resource()
        self.grant(self.a,read=True,write=True)
        refs=[dict(kind=x.kind,id=x.id) for x in (self.a,self.b)]
        with self.assertRaises(DomainError): self.act(self.actor,'resource.update',dict(sel,source_refs=refs),key='multi',revision=1)
        self.assertEqual(self.act(self.actor,'resource.read',sel).data['revision'],1)
