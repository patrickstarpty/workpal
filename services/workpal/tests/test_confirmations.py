from dataclasses import replace
from django.test import TestCase
from tests.access_support import AccessFixtures
from tests.test_actions import Input, restore_catalog
from workpal.actions import registry
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionRequest, ActionResult

class ConfirmationTests(AccessFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(restore_catalog, registry._specs.copy())
        registry._specs.clear()
        self.calls = 0
        def handler(*args):
            self.calls += 1
            return ActionResult('completed', [], {})
        registry.register(ActionSpec('confirm', Input, {'type':'object','properties':{},'additionalProperties':False}, handler, lambda *args: [], mutating=True, confirmation_required=True))

    def test_prepare_and_consume(self):
        request = ActionRequest('confirm', {'name':'x'}, None, 'key')
        first = registry.execute(self.actor, request)
        self.assertIn('confirmation_id', first.data)
        self.assertEqual(first, registry.execute(self.actor, request))
        self.assertEqual(self.calls, 0)
        request.confirmation_id = first.data['confirmation_id']
        self.assertEqual(registry.execute(self.actor, request).state, 'completed')
        registry.execute(self.actor, request)
        self.assertEqual(self.calls, 1)

    def prepare(self):
        return registry.execute(self.actor, ActionRequest('confirm', {'name':'x'}, None, 'key')).data['confirmation_id']

    def test_bindings_and_human_replay(self):
        from workpal.contracts import DomainError
        token = self.prepare()
        for changes in ({'confirmation_id':'bad'}, {'payload':{'name':'y'}},
                        {'idempotency_key':'other'}, {'expected_revision':1}):
            request = ActionRequest('confirm', {'name':'x'}, None, 'key', token)
            for key, value in changes.items():
                setattr(request, key, value)
            with self.assertRaises(DomainError):
                registry.execute(self.actor, request)
        request = ActionRequest('confirm', {'name':'x'}, None, 'key', token)
        with self.assertRaises(DomainError):
            registry.execute(replace(self.actor, executor_id='agent'), request)
        registry.execute(self.actor, request)
        with self.assertRaises(DomainError):
            registry.execute(replace(self.actor, executor_id='agent'), request)
        self.assertEqual(self.calls, 1)

    def test_expiry_does_not_renew(self):
        from datetime import timedelta
        from django.utils import timezone
        from workpal.actions.models import Confirmation
        from workpal.contracts import DomainError
        token = self.prepare()
        expiry = timezone.now() - timedelta(seconds=1)
        Confirmation.objects.filter(pk=token).update(expires_at=expiry)
        for confirmation in (None, token):
            with self.assertRaises(DomainError):
                registry.execute(self.actor, ActionRequest('confirm', {'name':'x'}, None, 'key', confirmation))
        self.assertEqual(Confirmation.objects.get().expires_at, expiry)

    def test_rollback_retry(self):
        from workpal.identity.models import Workspace
        from workpal.actions.models import Confirmation
        from workpal.audit.models import AuditEvent, Outbox
        token = self.prepare()
        spec = registry._specs['confirm']
        def fail(*args):
            Workspace.objects.create(name='rollback-confirm')
            raise RuntimeError('failure')
        registry._specs['confirm'] = replace(spec, handler=fail)
        request = ActionRequest('confirm', {'name':'x'}, None, 'key', token)
        with self.assertRaises(RuntimeError):
            registry.execute(self.actor, request)
        self.assertFalse(Confirmation.objects.get().consumed)
        self.assertFalse(Workspace.objects.filter(name='rollback-confirm').exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(Outbox.objects.exists())
        registry._specs['confirm'] = spec
        registry.execute(self.actor, request)

    def test_sources_and_revocation(self):
        from workpal.contracts import DomainError
        grant = self.grant(self.a, read=True, write=True)
        spec = replace(registry._specs['confirm'], resolve_refs=lambda *args:[self.a])
        registry._specs['confirm'] = spec
        token = self.prepare()
        grant.delete()
        request = ActionRequest('confirm', {'name':'x'}, None, 'key', token)
        with self.assertRaises(DomainError):
            registry.execute(self.actor, request)
        self.grant(self.a, read=True, write=True)
        registry._specs['confirm'] = replace(spec, resolve_refs=lambda *args:[])
        with self.assertRaises(DomainError):
            registry.execute(self.actor, request)
        self.assertEqual(self.calls, 0)

    def test_prepare_has_no_business_effects(self):
        from workpal.audit.models import AuditEvent, Outbox
        from workpal.actions.models import Confirmation, IdempotencyResult
        self.prepare()
        self.assertEqual(Confirmation.objects.count(), 1)
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(Outbox.objects.exists())
        self.assertFalse(IdempotencyResult.objects.exists())

    def test_read_confirmation_rejected(self):
        with self.assertRaises(ValueError):
            registry.register(replace(registry._specs['confirm'], action_id='bad', mutating=False))


from django.test import TransactionTestCase

class ConcurrentConfirmations(AccessFixtures, TransactionTestCase):
    def test_two_connections(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from workpal.identity.models import Workspace
        from workpal.audit.models import AuditEvent, Outbox
        self.addCleanup(restore_catalog, registry._specs.copy())
        registry._specs.clear()
        def handler(*args):
            Workspace.objects.create(name='confirmed-effect')
            return ActionResult('completed', [], {})
        registry.register(ActionSpec('concurrent-confirm', Input,
            {'type':'object','properties':{},'additionalProperties':False},
            handler, lambda *args:[], mutating=True, confirmation_required=True))
        request = ActionRequest('concurrent-confirm', {'name':'x'}, None, 'key')
        request.confirmation_id = registry.execute(self.actor, request).data['confirmation_id']
        barrier = Barrier(2)
        def consume(_):
            connections.close_all()
            try:
                barrier.wait()
                return registry.execute(self.actor, request)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(consume, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(Workspace.objects.filter(name='confirmed-effect').count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)
        self.assertEqual(Outbox.objects.count(), 1)
