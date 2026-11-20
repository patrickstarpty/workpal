from dataclasses import replace

from django.contrib.auth import get_user_model
from django.test import TestCase

from workpal.actions import registry
from workpal.actions.contracts import ActionSpec
from workpal.actions.models import Confirmation, IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import ActionRequest, ActionResult, DomainError
from workpal.identity.models import Membership, Workspace
from .access_support import AccessFixtures
from .test_actions import Input, restore_catalog


class ConfirmationReviewTests(AccessFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(restore_catalog, registry._specs.copy())
        registry._specs.clear()
        def handler(*args):
            Workspace.objects.create(name='confirmed mutation')
            return ActionResult('completed', [], {})
        self.spec = ActionSpec(
            'confirm.review', Input,
            {'type': 'object', 'properties': {}, 'additionalProperties': False},
            handler, lambda *args: [], mutating=True, confirmation_required=True,
        )
        registry.register(self.spec)

    def prepare(self, revision=None):
        request = ActionRequest('confirm.review', {'name': 'x'}, revision, 'key')
        result = registry.execute(self.actor, request)
        request.confirmation_id = result.data['confirmation_id']
        return request

    def test_agent_cannot_replay_confirmed_result_by_omitting_token(self):
        request = self.prepare()
        registry.execute(self.actor, request)
        request.confirmation_id = None
        with self.assertRaises(DomainError) as caught:
            registry.execute(replace(self.actor, executor_id='agent'), request)
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(Workspace.objects.filter(name='confirmed mutation').count(), 1)

    def test_token_cannot_be_submitted_to_an_unconfirmed_action(self):
        request = self.prepare()
        registry.register(replace(self.spec, action_id='ordinary', confirmation_required=False))
        request.action_id = 'ordinary'
        with self.assertRaises(DomainError):
            registry.execute(self.actor, request)
        self.assertFalse(Workspace.objects.filter(name='confirmed mutation').exists())
        self.assertFalse(Confirmation.objects.get().consumed)

    def test_token_is_bound_to_user_workspace_and_action(self):
        request = self.prepare()
        other_user = get_user_model().objects.create(username='another operator')
        Membership.objects.create(user=other_user, workspace=self.workspace, role='member')
        Membership.objects.create(user=self.user, workspace=self.other, role='member')
        registry.register(replace(self.spec, action_id='another.confirmation'))
        cases = (
            (replace(self.actor, user_id=other_user.pk), request),
            (replace(self.actor, workspace_id=self.other.pk), request),
            (self.actor, replace(request, action_id='another.confirmation')),
        )
        for actor, candidate in cases:
            with self.subTest(actor=actor, action=candidate.action_id):
                with self.assertRaises(DomainError) as caught:
                    registry.execute(actor, candidate)
                self.assertEqual(caught.exception.code, 'confirmation_conflict')
        self.assertFalse(Workspace.objects.filter(name='confirmed mutation').exists())
        self.assertFalse(Confirmation.objects.get().consumed)
        self.assertFalse(IdempotencyResult.objects.exists())

    def test_revision_cas_conflict_keeps_confirmation_unconsumed(self):
        from workpal.identity.service import rename_workspace
        self.member.role = 'owner'
        self.member.save()
        def handler(actor, payload, revision):
            rename_workspace(actor, actor.workspace_id, payload['name'], revision)
            return ActionResult('completed', [], {})
        registry._specs[self.spec.action_id] = replace(self.spec, handler=handler)
        request = self.prepare(revision=1)
        rename_workspace(self.actor, self.workspace.pk, 'concurrent change', 1)
        with self.assertRaises(DomainError) as caught:
            registry.execute(self.actor, request)
        self.assertEqual(caught.exception.code, 'revision_conflict')
        self.assertFalse(Confirmation.objects.get().consumed)
        self.assertFalse(IdempotencyResult.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(Outbox.objects.exists())
        self.workspace.refresh_from_db()
        self.assertEqual((self.workspace.name, self.workspace.revision), ('concurrent change', 2))
        with self.assertRaises(DomainError):
            registry.execute(self.actor, replace(request, expected_revision=2))
        retry = replace(request, expected_revision=2, idempotency_key='new', confirmation_id=None)
        retry.confirmation_id = registry.execute(self.actor, retry).data['confirmation_id']
        self.assertEqual(registry.execute(self.actor, retry).state, 'completed')
        self.workspace.refresh_from_db()
        self.assertEqual((self.workspace.name, self.workspace.revision), ('x', 3))

    def test_changed_role_and_revoked_membership_reject_consumption(self):
        registry._specs[self.spec.action_id] = replace(self.spec, allowed_roles=('owner',))
        self.member.role = 'owner'
        self.member.save()
        request = self.prepare()
        self.member.role = 'member'
        self.member.save()
        with self.assertRaises(DomainError) as caught:
            registry.execute(self.actor, request)
        self.assertEqual(caught.exception.status, 403)
        self.member.delete()
        with self.assertRaises(DomainError) as caught:
            registry.execute(self.actor, request)
        self.assertEqual(caught.exception.status, 404)
        self.assertFalse(Confirmation.objects.get().consumed)
        self.assertFalse(Workspace.objects.filter(name='confirmed mutation').exists())
