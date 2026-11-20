import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership

class IdentityAliasTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('alias-owner')
        self.workspace = Workspace.objects.create(name='Alias')
        Membership.objects.create(user=self.user, workspace=self.workspace, role='owner')
        self.client.force_login(self.user)
        self.base = f'/api/v1/workspaces/{self.workspace.pk}'

    def test_create_requires_explicit_confirmation(self):
        response = self.client.post(self.base+'/members', json.dumps(dict(username='pending', password='Secure-test-923', role='member')), content_type='application/json', HTTP_IDEMPOTENCY_KEY='alias-create')
        self.assertEqual(response.json().get('state'), 'waiting_confirmation')
        self.assertFalse(get_user_model().objects.filter(username='pending').exists())

    def test_missing_key_rejected(self):
        response = self.client.post(self.base, json.dumps(dict(name='Changed', revision=1)), content_type='application/json')
        self.assertEqual(response.status_code, 400)
