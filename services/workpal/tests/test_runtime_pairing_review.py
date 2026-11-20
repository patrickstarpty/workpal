from unittest.mock import patch

from django.test import TestCase
from tests import test_runtime_pairing as fixtures
from workpal.access.models import RegisteredObject, SourceLink, SourceGrant
from workpal.access.service import register_object
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError, ObjectRef
from workpal.agents import runtime_identity as core
from workpal.agents.models import Runtime, RuntimePairing


class RuntimePairingReviewTests(TestCase):
    setUp = fixtures.RuntimePairingTests.setUp
    pair = fixtures.RuntimePairingTests.pair

    def snapshot(self):
        models = (Runtime, RuntimePairing, RegisteredObject, SourceLink,
                  SourceGrant, AuditEvent, Outbox, IdempotencyResult)
        return {m._meta.label: list(m.objects.order_by('pk').values()) for m in models}

    def test_empty_executor_is_not_a_human_identity(self):
        _, runtime = self.pair()
        machine = Actor(self.user.pk, self.workspace.pk, executor_id='')
        for operation in (lambda: core.issue_pairing(machine, 'Device'),
                          lambda: core.revoke(machine, runtime['runtime_id'], 1)):
            with self.subTest(operation=operation):
                before = self.snapshot()
                with self.assertRaises(DomainError) as caught:
                    operation()
                self.assertEqual(caught.exception.status, 403)
                self.assertEqual(self.snapshot(), before)

    def test_consumption_preserves_retryable_storage_failure(self):
        issued = core.issue_pairing(self.actor, 'Device')
        before = self.snapshot()
        failure = DomainError('storage_unavailable', 'Unavailable.', status=503, retryable=True)
        with patch.object(core, 'require_member', side_effect=failure):
            with self.assertRaises(DomainError) as caught:
                core.consume_pairing(issued['secret'])
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.snapshot(), before)
        self.assertGreater(core.consume_pairing(issued['secret'])['runtime_id'], 0)

    def test_audit_contains_registered_object_and_current_source_scope(self):
        issued = core.issue_pairing(self.actor, 'Device')
        pairing_ref = ObjectRef('runtime_pairing', str(issued['pairing_id']))
        source_ref = ObjectRef('source', 'pairing-review')
        register_object(self.workspace.pk, source_ref, is_source=True)
        register_object(self.workspace.pk, pairing_ref, [source_ref])
        runtime = core.consume_pairing(issued['secret'])
        expected = [dict(kind='runtime_pairing', id=str(issued['pairing_id'])),
                    dict(kind='runtime', id=str(runtime['runtime_id']))]
        event = AuditEvent.objects.get(action_id='runtime.pairing.consume')
        self.assertEqual(event.outcome, 'completed')
        self.assertCountEqual(event.object_refs, expected)
        self.assertCountEqual(event.scope_refs, expected + [dict(kind='source', id='pairing-review')])
        outbox = Outbox.objects.get(event=event)
        self.assertEqual(outbox.object_refs, event.object_refs)
        self.assertEqual(outbox.scope_refs, event.scope_refs)
        issue_event = AuditEvent.objects.get(action_id='runtime.pairing.issue')
        self.assertEqual(issue_event.object_refs, [expected[0]])
        self.assertEqual(issue_event.scope_refs, [expected[0]])

    def test_removed_or_disabled_issuer_does_not_consume_pairing(self):
        issued = core.issue_pairing(self.actor, 'Device')
        for disabled in (True, False):
            with self.subTest(disabled=disabled):
                if disabled:
                    self.user.is_active = False
                    self.user.save(update_fields=['is_active'])
                else:
                    self.member.delete()
                before = self.snapshot()
                with self.assertRaises(DomainError) as caught:
                    core.consume_pairing(issued['secret'])
                self.assertEqual(caught.exception.status, 403)
                self.assertEqual(self.snapshot(), before)
                self.user.is_active = True
                self.user.save(update_fields=['is_active'])

    def test_current_read_and_write_are_separate(self):
        _, runtime = self.pair()
        pk = runtime['runtime_id']
        source = ObjectRef('source', 'runtime-review')
        register_object(self.workspace.pk, source, is_source=True)
        root = RegisteredObject.objects.get(kind=source.kind, object_id=source.id)
        grant = SourceGrant.objects.create(source=root, user=self.user, read=True, write=False)
        register_object(self.workspace.pk, ObjectRef('runtime', str(pk)), [source])
        self.assertFalse(core.read_runtime(self.actor, pk)['revoked'])
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            core.revoke(self.actor, pk, 1)
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
        grant.write = True
        grant.save(update_fields=['write'])
        self.assertTrue(core.revoke(self.actor, pk, 1)['revoked'])
        grant.read = False
        grant.save(update_fields=['read'])
        with self.assertRaises(DomainError):
            core.read_runtime(self.actor, pk)

    def test_actual_audit_failure_restores_complete_rows(self):
        original = core.audit.record
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('storage_unavailable', 'Unavailable.', status=503)
        before = self.snapshot()
        with patch.object(core.audit, 'record', side_effect=fail):
            with self.assertRaises(DomainError):
                core.issue_pairing(self.actor, 'Device')
        self.assertEqual(self.snapshot(), before)
        issued = core.issue_pairing(self.actor, 'Device')
        before = self.snapshot()
        with patch.object(core.audit, 'record', side_effect=fail):
            with self.assertRaises(DomainError):
                core.consume_pairing(issued['secret'])
        self.assertEqual(self.snapshot(), before)
        core.consume_pairing(issued['secret'])
        self.assertEqual(Runtime.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action_id='runtime.pairing.consume').count(), 1)
