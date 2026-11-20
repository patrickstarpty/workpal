from django.test import TestCase, Client

class IdentityTests(TestCase):
    def test_login_get_is_read_only(self):
        self.assertEqual(Client().get('/api/v1/auth/login').status_code, 405)

    def test_schema_rejects_array(self):
        self.assertEqual(Client().post('/api/v1/auth/login', '[]', content_type='application/json').status_code, 400)

    def test_csrf_rejects_write(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post('/api/v1/auth/login', {}, content_type='application/json').status_code, 403)
