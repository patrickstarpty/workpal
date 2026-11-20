from io import StringIO
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from workpal.identity.models import Workspace, Membership

class BootstrapTests(TestCase):
    @override_settings(AUTH_PASSWORD_VALIDATORS=[])
    def test_stdin_and_repeat(self):
        call_command('bootstrap_workspace', username='first', name='Local', password_stdin=True, stdin=StringIO('secure-password\n'))
        self.assertTrue(Membership.objects.get().user.check_password('secure-password'))
        with self.assertRaises(CommandError):
            call_command('bootstrap_workspace', username='second', name='Again', password_stdin=True, stdin=StringIO('secure-password\n'))
        self.assertEqual(Workspace.objects.count(),1)
