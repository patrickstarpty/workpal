from django.test import TestCase
from django.contrib.auth import get_user_model

class SessionContextTests(TestCase):
    def test_authenticated_context(self):
        user = get_user_model().objects.create_user(username='session-user', password='secret')
        self.client.force_login(user)
        response = self.client.get('/api/v1/auth/session')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'user': {'id': user.pk, 'username': user.username}, 'workspaces': []})
