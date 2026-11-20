from unittest.mock import patch
from django.apps import apps
from django.db import connection, transaction
from tests.support import WorkpalCase
from tests.access_support import AccessFixtures
from workpal.contracts import Actor, DomainError
from workpal.agents import service as agents
from workpal.agents.models import Agent
from workpal.identity.models import Membership
from workpal.execution.admission import admit_initialization


class InitializationAdmission(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()
        self.agent = agents.create(self.actor, 'Builder')
        self.register(self.workspace.pk, agents.ref(self.agent['id']), [self.b, self.a])
        self.ga = self.grant(self.a, read=True)
        self.gb = self.grant(self.b, read=True)

    def admit(self):
        return admit_initialization(self.actor, self.agent['id'])

    def error(self, status, operation):
        with self.assertRaises(DomainError) as caught:
            operation()
        self.assertEqual(caught.exception.status, status)

    def snapshot(self):
        with connection.cursor() as cursor:
            result = {}
            for table in connection.introspection.table_names():
                cursor.execute('SELECT * FROM ' + connection.ops.quote_name(table))
                result[table] = sorted(map(repr, cursor.fetchall()))
            return result

    def test_without_runtime_configuration_only(self):
        result = self.admit()
        self.assertEqual(result.agent, agents.read(self.actor, self.agent['id']))
        self.assertEqual(result.source_refs, (self.a, self.b))
        self.assertEqual(result.purpose, 'initialized')
        self.assertIs(result.execution_authorized, False)
        from dataclasses import FrozenInstanceError
        with self.assertRaises(FrozenInstanceError):
            result.purpose = 'running'

    def test_all_extension_providers(self):
        for provider in agents.PROVIDERS[1:]:
            Agent.objects.filter(pk=self.agent['id']).update(provider_key=provider)
            self.error(409, self.admit)

    def test_current_source_member_and_cross_workspace(self):
        self.member.role = 'member'
        self.member.save()
        self.admit()
        self.ga.read = False
        self.ga.save()
        self.error(403, self.admit)
        self.ga.read = True
        self.ga.save()
        self.user.is_active = False
        self.user.save()
        self.error(404, self.admit)
        self.user.is_active = True
        self.user.save()
        Membership.objects.create(user=self.user, workspace=self.other, role='member')
        self.error(404, lambda: admit_initialization(Actor(self.user.pk, self.other.pk), self.agent['id']))
        self.member.delete()
        self.error(404, self.admit)

    def test_ids_configuration_and_copy(self):
        for value in [True, False, '1', 0, -1, 2**63, None, 1.0]:
            self.error(400, lambda: admit_initialization(self.actor, value))
        self.error(404, lambda: admit_initialization(self.actor, 999999))
        for field, value in [('name', ''), ('name', '  '), ('name', 'a'*201), ('model', 'a'*201), ('provider_key', 'unknown')]:
            with transaction.atomic():
                Agent.objects.filter(pk=self.agent['id']).update(**{field: value})
                self.error(400, self.admit)
                transaction.set_rollback(True)
        for field in ['name', 'model', 'provider_key']:
            dto = dict(self.agent, **{field: None})
            with patch.object(agents, 'read', return_value=dto):
                self.error(400, self.admit)
        Agent.objects.filter(pk=self.agent['id']).update(name='a'*200, model='m'*200)
        self.admit()
        result = self.admit()
        result.agent['name'] = 'mutated'
        self.assertEqual(self.admit().agent['name'], 'a'*200)
        self.assertEqual(agents.read(self.actor, self.agent['id'])['name'], 'a'*200)

    def test_all_tables_unchanged(self):
        before = self.snapshot()
        self.admit()
        self.assertEqual(before, self.snapshot())

    def test_transaction_repetition_rollback_and_storage_failure(self):
        before = self.snapshot()
        with transaction.atomic():
            self.assertEqual(self.admit(), self.admit())
            transaction.set_rollback(True)
        self.assertEqual(before, self.snapshot())
        with patch('workpal.execution.admission.authorize', side_effect=DomainError('storage_unavailable', 'Unavailable', status=503)):
            self.error(503, self.admit)
        self.assertEqual(before, self.snapshot())
