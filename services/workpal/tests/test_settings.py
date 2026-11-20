import json
import os
from pathlib import Path
import subprocess
import sys
from django.test import SimpleTestCase


class SettingsTests(SimpleTestCase):
    def inspect(self, **env):
        clean = {k: v for k, v in os.environ.items() if not k.startswith('WORKPAL_')}
        clean.update(env)
        return subprocess.run([sys.executable, '-c', 'import config.settings as s; import json; print(json.dumps([s.ALLOWED_HOSTS,s.SESSION_COOKIE_SECURE,s.CSRF_COOKIE_SECURE,s.SECURE_SSL_REDIRECT,s.SECURE_HSTS_SECONDS,len(s.AUTH_PASSWORD_VALIDATORS),str(s.DATABASES["default"]["NAME"])]))'], cwd=Path(__file__).resolve().parents[1], env=clean, capture_output=True, text=True)

    def test_development(self):
        result = self.inspect(WORKPAL_DB_PATH='/tmp/explicit.sqlite3')
        self.assertEqual(result.returncode, 0, result.stderr)
        hosts, *values = json.loads(result.stdout)
        self.assertEqual(hosts, ['localhost', '127.0.0.1', '[::1]'])
        self.assertEqual(values, [False, False, False, 0, 4, '/tmp/explicit.sqlite3'])

    def test_production_requires_configuration(self):
        for env in ({}, {'WORKPAL_SECRET_KEY': 'x'*50}, {'WORKPAL_SECRET_KEY': 'short', 'WORKPAL_ALLOWED_HOSTS': 'example.com'}):
            self.assertNotEqual(self.inspect(WORKPAL_ENV='production', **env).returncode, 0)

    def test_production_security(self):
        result = self.inspect(WORKPAL_ENV='production', WORKPAL_SECRET_KEY='x'*50, WORKPAL_ALLOWED_HOSTS='example.com')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[:6], [['example.com'], True, True, True, 31536000, 4])
