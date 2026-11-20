from tests.support import identity_post
import json
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership, LoginAttempt
from django.utils import timezone
from datetime import timedelta

@override_settings(AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':8}}])
class MembershipTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('owner', password='Secure-test-923')
        self.workspace = Workspace.objects.create(name='One')
        self.owner = Membership.objects.create(user=self.user, workspace=self.workspace, role='owner')
        self.client = Client(enforce_csrf_checks=True)
        self.base = f'/api/v1/workspaces/{self.workspace.pk}'

    def post(self, path, data):
        token = self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        return identity_post(self.client, path, data, token)

    def login(self):
        return self.post('/api/v1/auth/login', {'username':'owner','password':'Secure-test-923'})

    def test_login_rotation_logout_and_disabled(self):
        self.client.get('/api/v1/auth/csrf')
        before = self.client.cookies['csrftoken'].value
        self.assertEqual(self.login().status_code, 200)
        self.assertNotEqual(before, self.client.cookies['csrftoken'].value)
        self.assertEqual(self.post('/api/v1/auth/logout', {}).status_code, 200)
        self.assertEqual(self.client.get(self.base).status_code, 403)
        self.login()
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get(self.base).status_code, 403)

    def test_limit_and_expiry(self):
        for _ in range(5):
            self.assertEqual(self.post('/api/v1/auth/login', {'username':'missing','password':'wrong'}).status_code,403)
        self.assertEqual(self.post('/api/v1/auth/login', {'username':'missing','password':'wrong'}).status_code,429)
        LoginAttempt.objects.update(updated=timezone.now()-timedelta(minutes=6))
        self.assertEqual(self.post('/api/v1/auth/login', {'username':'missing','password':'wrong'}).status_code,403)

    def test_management(self):
        self.login()
        path = self.base+'/members'
        response = self.post(path, {'username':'new','password':'Secure-test-923','role':'member'})
        self.assertEqual(response.status_code,200, response.content)
        target = response.json()['id']
        self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(self.post(f'{path}/{target}', {'role':'admin','revision':2}).status_code,409)
        self.assertEqual(self.post(f'{path}/{target}', {'role':'admin','revision':True}).status_code,400)
        self.assertEqual(self.post(f'{path}/{self.owner.pk}', {'role':'member','revision':1}).status_code,409)
        self.assertEqual(self.post(f'{path}/{target}/revoke', {'revision':1}).status_code,200)
        other = Workspace.objects.create(name='Other')
        self.assertEqual(self.client.get(f'/api/v1/workspaces/{other.pk}').status_code,404)
        self.owner.role='member'; self.owner.save()
        self.assertEqual(self.client.get(path).status_code,403)

    def test_revoke_sessions(self):
        self.login()
        self.assertEqual(self.post('/api/v1/auth/revoke-sessions', {}).status_code,200)
        self.assertEqual(self.client.get(self.base).status_code,403)
