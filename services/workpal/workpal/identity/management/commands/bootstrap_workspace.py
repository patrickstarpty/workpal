import getpass
import sys
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from workpal.identity.models import Workspace, Membership

class Command(BaseCommand):
    stealth_options = ('stdin',)
    help = 'Create the initial local workspace and owner.'

    def execute(self, *args, **options):
        self.input_stream = options.pop("stdin", sys.stdin)
        return super().execute(*args, **options)

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--name', required=True)
        parser.add_argument('--password-stdin', action='store_true')

    def handle(self, *args, **options):
        password = self.input_stream.readline().rstrip('\r\n') if options['password_stdin'] else getpass.getpass('Password: ')
        user = get_user_model()(username=options['username'])
        try:
            user.full_clean(exclude=['password'])
            validate_password(password, user)
            if not password or not options['name'].strip() or len(options['name']) > 200:
                raise CommandError('Invalid account or workspace details.')
            user.set_password(password)
            with transaction.atomic():
                if Workspace.objects.exists():
                    raise CommandError('Workspace already initialized.')
                user.save()
                workspace = Workspace.objects.create(name=options['name'])
                Membership.objects.create(workspace=workspace, user=user, role='owner')
        except ValidationError:
            raise CommandError('Invalid account details.')
