from dataclasses import replace

from django import forms
from django.test import TestCase

from workpal.actions import registry
from workpal.actions.contracts import ActionSpec
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import ActionRequest, ActionResult, DomainError
from .access_support import AccessFixtures


class ActionReviewTests(AccessFixtures, TestCase):
    def setUp(self):
        super().setUp()
        previous = registry._specs.copy()
        registry._specs.clear()
        self.addCleanup(self.restore_catalog, previous)
        class Input(forms.Form):
            name = forms.CharField(max_length=30)
            api_key = forms.CharField(required=False)
        self.spec = ActionSpec(
            'review.record', Input,
            {'type': 'object', 'properties': {'name': {'type': 'string'}},
             'required': ['name'], 'additionalProperties': False},
            lambda actor, payload, revision: ActionResult('completed', [], {'name': payload['name']}),
            lambda actor, payload: [], mutating=True,
        )
        registry.register(self.spec)

    @staticmethod
    def restore_catalog(previous):
        registry._specs.clear()
        registry._specs.update(previous)

    def execute(self, payload=None):
        return registry.execute(self.actor, ActionRequest('review.record', payload or {'name': 'x'}, None, 'key'))

    def test_replay_preserves_original_scope_when_resolver_changes(self):
        grant = self.grant(self.a, read=True, write=True)
        registry._specs['review.record'] = replace(self.spec, resolve_refs=lambda actor, payload: [self.a])
        self.execute()
        # A project binding may change; old cached output still came from A.
        registry._specs['review.record'] = self.spec
        grant.delete()
        with self.assertRaises(DomainError):
            self.execute()

    def test_audit_and_outbox_keep_input_scope_without_result_objects(self):
        self.grant(self.a, read=True, write=True)
        registry._specs['review.record'] = replace(self.spec, resolve_refs=lambda actor, payload: [self.direct])
        self.execute()
        expected = {'kind': self.a.kind, 'id': self.a.id}
        self.assertIn(expected, AuditEvent.objects.get().scope_refs)
        self.assertIn(expected, Outbox.objects.get().scope_refs)

    def test_sensitive_audit_field_is_excluded_even_if_allowlisted(self):
        registry._specs['review.record'] = replace(self.spec, audit_fields=('name', 'api_key'))
        self.execute({'name': 'visible', 'api_key': 'synthetic-test-credential'})
        self.assertEqual(AuditEvent.objects.get().fields, {'name': 'visible'})

    def test_reads_do_not_enqueue_business_dispatch(self):
        registry._specs['review.record'] = replace(self.spec, mutating=False)
        self.execute()
        self.assertEqual(AuditEvent.objects.count(), 1)
        self.assertEqual(Outbox.objects.count(), 0)

    def test_invalid_result_state_rolls_back_handler_writes(self):
        from workpal.identity.models import Workspace
        def handler(*args):
            Workspace.objects.create(name='must roll back')
            return ActionResult('imaginary_success', [], {'name': 'x'})
        registry._specs['review.record'] = replace(self.spec, handler=handler)
        with self.assertRaises(ValueError):
            self.execute()
        self.assertFalse(Workspace.objects.filter(name='must roll back').exists())
        self.assertFalse(Outbox.objects.exists())

    def test_action_can_revoke_the_object_it_authorized(self):
        from workpal.access.models import RegisteredObject
        self.grant(self.a, read=True, write=True)
        def handler(*args):
            RegisteredObject.objects.filter(kind=self.direct.kind, object_id=self.direct.id).update(available=False)
            return ActionResult('completed', [], {'name': 'revoked'})
        registry._specs['review.record'] = replace(
            self.spec, resolve_refs=lambda actor, payload: [self.direct], handler=handler)
        self.assertEqual(self.execute().state, 'completed')
        self.assertIn({'kind': self.a.kind, 'id': self.a.id}, AuditEvent.objects.get().scope_refs)
