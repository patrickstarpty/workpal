from django.test import TransactionTestCase
from tests.access_support import AccessFixtures
from workpal.actions import registry
from workpal.contracts import ActionRequest

class IdentityActionsTests(AccessFixtures, TransactionTestCase):
    def test_read_registered_on_startup(self):
        result = registry.execute(self.actor, ActionRequest('workspace.read', {}, None, None))
        self.assertEqual(result.data['name'], 'one')

    def owner(self):
        self.member.role = 'owner'
        self.member.save()

    def call(self, action, payload, revision=None, key='key', token=None):
        return registry.execute(self.actor, ActionRequest(action, payload, revision, key, token))

    def test_catalog(self):
        def identity_ids():
            return {s['action_id'] for s in registry.catalog(self.actor)
                    if s['action_id'].startswith(('workspace.', 'member.'))}
        self.assertEqual(identity_ids(), {'workspace.read', 'workspace.people.list', 'workspace.people.read'})
        self.owner()
        self.assertEqual(identity_ids(), {'workspace.read', 'workspace.people.list', 'workspace.people.read', 'workspace.rename', 'member.list',
                                          'member.create', 'member.set_role', 'member.revoke'})

    def test_rename(self):
        from workpal.contracts import DomainError
        from workpal.audit.models import AuditEvent, Outbox
        self.owner()
        revision = self.workspace.revision
        result = self.call('workspace.rename', {'name': 'new'}, revision)
        self.assertEqual(result.data['revision'], revision + 1)
        self.assertEqual(self.call('workspace.rename', {'name': 'new'}, revision), result)
        self.assertEqual(AuditEvent.objects.count(), 1)
        self.assertEqual(Outbox.objects.count(), 1)
        for name, key in [('other', 'key'), ('new', 'fresh')]:
            with self.assertRaises(DomainError) as error:
                self.call('workspace.rename', {'name': name}, revision, key)
            self.assertEqual(error.exception.status, 409)

    def test_revision_validation(self):
        from workpal.contracts import DomainError
        from workpal.actions.models import Confirmation
        self.owner()
        for action, payload in [('workspace.rename', {'name': 'x'}), ('member.set_role', {'membership_id': self.member.pk, 'role': 'member'}), ('member.revoke', {'membership_id': self.member.pk})]:
            for revision in [None, 0, True]:
                with self.assertRaises(DomainError):
                    self.call(action, payload, revision)
        self.assertEqual(Confirmation.objects.count(), 0)

    def test_self_revoke(self):
        from django.contrib.auth import get_user_model
        from workpal.identity.models import Membership
        from workpal.contracts import DomainError
        self.owner()
        Membership.objects.create(user=get_user_model().objects.create(username='second'), workspace=self.workspace, role='owner')
        payload = {'membership_id': self.member.pk}
        waiting = self.call('member.revoke', payload, self.member.revision)
        self.assertTrue(Membership.objects.filter(pk=self.member.pk).exists())
        result = self.call('member.revoke', payload, self.member.revision, token=waiting.data['confirmation_id'])
        self.assertEqual(result.data, {})
        self.assertFalse(Membership.objects.filter(pk=self.member.pk).exists())
        with self.assertRaises(DomainError) as caught:
            self.call('workspace.read', {})
        self.assertEqual(caught.exception.status, 404)
        with self.assertRaises(DomainError) as caught:
            self.call('member.revoke', payload, self.member.revision, token=waiting.data['confirmation_id'])
        self.assertEqual(caught.exception.status, 404)

    def test_member_lifecycle_and_secrets(self):
        import json
        from django.contrib.auth import get_user_model
        from workpal.identity.models import Membership
        from workpal.actions.models import Confirmation, IdempotencyResult
        from workpal.audit.models import AuditEvent, Outbox
        self.owner()
        secret = 'Long-Unique-Password-928!'
        payload = dict(username='newuser', password=secret, role='member')
        waiting = self.call('member.create', payload)
        self.assertFalse(get_user_model().objects.filter(username='newuser').exists())
        result = self.call('member.create', payload, token=waiting.data['confirmation_id'])
        target = Membership.objects.get(pk=result.data['id'])
        self.assertTrue(target.user.check_password(secret))
        for action, fields in [('member.set_role', dict(membership_id=target.pk, role='admin')), ('member.revoke', dict(membership_id=target.pk))]:
            target.refresh_from_db()
            waiting = self.call(action, fields, target.revision)
            self.assertTrue(Membership.objects.filter(pk=target.pk, role=target.role).exists())
            self.call(action, fields, target.revision, token=waiting.data['confirmation_id'])
        for model in (Confirmation, IdempotencyResult, AuditEvent, Outbox):
            self.assertNotIn(secret, json.dumps(list(model.objects.values()), default=str))
        self.assertNotIn(secret, json.dumps(result.data))

    def test_service_guards_on_confirmation(self):
        from django.contrib.auth import get_user_model
        from workpal.identity.models import Membership
        from workpal.contracts import DomainError
        self.owner()
        foreign = Membership.objects.create(user=get_user_model().objects.create(username='foreign'), workspace=self.other, role='member')
        for target in (self.member, foreign):
            payload = {'membership_id': target.pk}
            waiting = self.call('member.revoke', payload, target.revision, str(target.pk))
            with self.assertRaises(DomainError):
                self.call('member.revoke', payload, target.revision, str(target.pk), waiting.data['confirmation_id'])
            self.assertTrue(Membership.objects.filter(pk=target.pk).exists())
        owner = Membership.objects.create(user=get_user_model().objects.create(username='owner'), workspace=self.workspace, role='owner')
        self.member.role = 'admin'
        self.member.save()
        payload = dict(membership_id=owner.pk, role='member')
        waiting = self.call('member.set_role', payload, owner.revision)
        with self.assertRaises(DomainError):
            self.call('member.set_role', payload, owner.revision, token=waiting.data['confirmation_id'])
