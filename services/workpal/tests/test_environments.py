from django.test import TestCase
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership
from workpal.contracts import Actor, ActionRequest
from workpal.actions.registry import execute

class EnvironmentTests(TestCase):
    def setUp(self):
        u=get_user_model().objects.create(username='owner')
        w=Workspace.objects.create(name='w')
        Membership.objects.create(user=u,workspace=w,role='owner')
        self.actor=Actor(u.pk,w.pk)
        self.p=execute(self.actor,ActionRequest('project.create',{'name':'p'},None,'p')).data['id']
    def test_registry_create(self):
        result=execute(self.actor,ActionRequest('environment.create',dict(project_id=self.p,name='SIT',timezone='UTC'),None,'e'))
        self.assertEqual(result.data['name'],'SIT')
