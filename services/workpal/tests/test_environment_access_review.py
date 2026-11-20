from django.test import TestCase
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership
from workpal.contracts import Actor, DomainError
from workpal.work import service as projects
from workpal.investigation import environments as e

class EnvironmentAccessReview(TestCase):
    def setUp(self):
        u=get_user_model().objects.create(username='review')
        w=Workspace.objects.create(name='review')
        Membership.objects.create(user=u,workspace=w,role='owner')
        self.a=Actor(u.pk,w.pk)
        self.p=projects.create(self.a,'p')['id']
    def test_strict_ids(self):
        for pk in (True,'1',0,-1,2**63):
            with self.subTest(pk=pk), self.assertRaises(DomainError): e.read(self.a,pk)
    def test_existing_defaults_validate_timezone(self):
        e.ensure_defaults(self.a,self.p,'UTC')
        with self.assertRaises(DomainError): e.ensure_defaults(self.a,self.p,'invalid/zone')
    def test_inactive_target(self):
        target=get_user_model().objects.create(username='inactive',is_active=False)
        Membership.objects.create(user=target,workspace_id=self.a.workspace_id,role='member')
        row=e.create(self.a,self.p,'SIT','UTC')
        with self.assertRaises(DomainError): e.grant(self.a,row['id'],target.pk,True,False,False,1)
