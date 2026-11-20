"""Independent public renew review; inherited fixture tests deliberately disabled."""
from tests import test_runtime_lease_claim as fixtures
from unittest.mock import patch
from dataclasses import asdict
from datetime import timedelta, datetime
from workpal.execution import leases
from workpal.execution.models import TaskToken, Run
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import DomainError

class RenewReviewTests(fixtures.ClaimTests):
    test_default_and_strict_reports = None
    test_claim_identity_and_no_redispatch = None
    test_persistent_scan_skips_denied_sources = None

    def setUp(self):
        super().setUp()
        self.row = self.create_run('private-renew-review-body')
        self.clock = patch.object(leases, '_clock', return_value=self.now)
        self.clock_mock = self.clock.start(); self.addCleanup(self.clock.stop)
        self.verifier = patch.object(leases, '_verify_capabilities', return_value=True)
        self.verifier.start(); self.addCleanup(self.verifier.stop)
        self.lease = self.claim().lease

    def renew(self, **kwargs):
        return leases.renew(kwargs.pop('secret', self.lease.task_token),
                            run_id=kwargs.pop('run_id', self.row.pk), epoch=kwargs.pop('epoch', 1))

    def test_two_rotations_and_lost_response(self):
        from workpal.actions.models import IdempotencyResult
        from django.core.cache import cache
        cache_before = (list(IdempotencyResult.objects.values()), dict(getattr(cache, '_cache', {})))
        old_scope = TaskToken.objects.get(run=self.row).scope_refs
        for index in range(2):
            secret = self.lease.task_token
            self.clock_mock.reset_mock()
            result = self.renew()
            self.assertEqual(self.clock_mock.call_count, 1)
            self.assertNotIn('input_snapshot', asdict(result.lease))
            self.assertEqual(result.lease.expires_at, self.now + timedelta(seconds=45))
            token = TaskToken.objects.get(run=self.row, revoked_at=None)
            self.assertEqual(token.expires_at, self.now + timedelta(seconds=60))
            self.assertTrue(all(v in token.scope_refs for v in old_scope))
            before = self.snapshot()
            self.assertEqual(self.renew(secret=secret).status, 401)
            self.assertEqual(before, self.snapshot())
            self.lease = result.lease
        self.row.refresh_from_db()
        self.assertEqual((self.row.status, self.row.lease_epoch, self.row.revision), ('dispatched', 1, 4))
        self.assertEqual(AuditEvent.objects.filter(action_id='runtime.renew').count(), 2)
        self.assertEqual(Outbox.objects.filter(event__action_id='runtime.renew').count(), 2)
        self.assertEqual(cache_before, (list(IdempotencyResult.objects.values()), dict(getattr(cache, '_cache', {}))))
        emitted = repr(list(AuditEvent.objects.values())) + repr(list(Outbox.objects.values()))
        for token in TaskToken.objects.all():
            self.assertNotIn(token.secret_hash, emitted)
        self.assertNotIn('private-renew-review-body', emitted)
        self.assertNotIn(self.lease.task_token, emitted)

    def test_strict_identifiers_and_revision_zero_write(self):
        for field in ('run_id', 'epoch'):
            for value in (True, -1, 0, 2**63, '1'):
                before = self.snapshot()
                with self.assertRaises(DomainError) as error: self.renew(**{field: value})
                self.assertEqual(error.exception.status, 400)
                self.assertEqual(before, self.snapshot())
        Run.objects.filter(pk=self.row.pk).update(revision=2**31-1)
        before = self.snapshot()
        with self.assertRaises(DomainError) as error: self.renew()
        self.assertEqual(error.exception.status, 400)
        self.assertEqual(before, self.snapshot())

    def test_clock_and_token_equality(self):
        for now in (datetime(2026, 1, 1), self.now + timedelta(seconds=60)):
            before = self.snapshot()
            with patch.object(leases, '_clock', return_value=now):
                if now.tzinfo is None:
                    with self.assertRaises(DomainError) as error: self.renew()
                    self.assertEqual(error.exception.status, 400)
                else: self.assertEqual(self.renew().status, 401)
            self.assertEqual(before, self.snapshot())
        with patch.object(leases, '_clock', return_value=self.now + timedelta(seconds=45)):
            self.assertEqual(self.renew().reason, 'lease_expired')
        self.row.refresh_from_db(); self.assertEqual(self.row.status, 'recovery_required')

    def test_verifier_failures_preserve_transaction(self):
        for value in (DomainError('storage_unavailable', 'Unavailable', status=503), None, 1):
            before = self.snapshot()
            options = {'side_effect': value} if isinstance(value, Exception) else {'return_value': value}
            with patch.object(leases, '_verify_capabilities', **options):
                with self.assertRaises(DomainError) as error: self.renew()
            self.assertEqual(error.exception.status, 503 if isinstance(value, Exception) else 400)
            self.assertEqual(before, self.snapshot())

    def test_real_audit_failure_rotation_and_stop(self):
        original = leases.audit.record
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('storage_unavailable', 'Unavailable', status=503)
        for stopping in (False, True):
            if stopping: self.member.delete()
            before = self.snapshot()
            with patch.object(leases.audit, 'record', side_effect=fail):
                with self.assertRaises(DomainError) as error: self.renew()
            self.assertEqual(error.exception.status, 503)
            self.assertEqual(before, self.snapshot())
        self.assertEqual(self.renew().reason, 'authorization_revoked')

    def test_corrupt_scope_fails_closed_rotation_and_stop(self):
        token = TaskToken.objects.get(run=self.row)
        for scope in ([{'kind':'source','id':'missing-private-reference'}], [{'kind':'source'}]):
            TaskToken.objects.filter(pk=token.pk).update(scope_refs=scope)
            for status in ('dispatched', 'cancel_requested'):
                Run.objects.filter(pk=self.row.pk).update(status=status)
                before = self.snapshot()
                with self.assertRaises(DomainError) as error: self.renew()
                self.assertEqual(error.exception.status, 503)
                self.assertEqual(before, self.snapshot())

    def test_two_real_file_connections_rotate_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from pathlib import Path
        from django.db import connections
        barrier = Barrier(2)
        def worker():
            connection = connections['default']
            try:
                connection.ensure_connection(); raw = connection.connection
                self.assertTrue(Path(connection.settings_dict['NAME']).is_file())
                barrier.wait(timeout=15)
                try: result = self.renew()
                except DomainError as error:
                    self.assertEqual((error.code, error.status), ('storage_busy', 503))
                    result = self.renew()
                return raw, result
            finally: connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
        self.assertIsNot(results[0][0], results[1][0])
        self.assertEqual(sorted(result.kind for _, result in results), ['denied', 'renewed'])
        self.assertEqual(TaskToken.objects.filter(run=self.row, revoked_at=None).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action_id='runtime.renew').count(), 1)
        self.assertEqual(Outbox.objects.filter(event__action_id='runtime.renew').count(), 1)
        self.row.refresh_from_db(); self.assertEqual(self.row.revision, 3)


def revocation_case(mode):
    def test(self):
        from workpal.agents.models import Agent
        from workpal.agents import runtime_identity as devices, service as agents
        from workpal.access.models import RegisteredObject, SourceGrant
        from workpal.execution import service as runs
        if mode in ('read', 'write', 'available'):
            self.register(self.workspace.pk, agents.ref(self.agent['id']), [self.a])
            self.grant(self.a, read=True, write=True)
            if mode == 'available':
                RegisteredObject.objects.filter(workspace=self.workspace, kind=self.a.kind, object_id=self.a.id).update(available=False)
            else:
                SourceGrant.objects.filter(user=self.user).update(**{mode:False})
        elif mode == 'member': self.member.delete()
        elif mode == 'provider': Agent.objects.filter(pk=self.agent['id']).update(provider_key='codex_cli')
        elif mode == 'rebind':
            other = devices.consume_pairing(devices.issue_pairing(self.actor, 'Other')['secret'])
            devices.bind(self.actor, self.agent['id'], other['runtime_id'], Agent.objects.get(pk=self.agent['id']).revision)
        before_input = (self.row.input_snapshot, self.row.sha256)
        result = self.renew()
        self.assertEqual(result.reason, 'authorization_revoked')
        self.row.refresh_from_db()
        self.assertEqual((self.row.input_snapshot, self.row.sha256), before_input)
        self.assertEqual(self.row.status, 'cancel_requested')
        self.assertFalse(TaskToken.objects.filter(run=self.row, revoked_at=None).exists())
        event = AuditEvent.objects.get(action_id='runtime.renew')
        self.assertEqual(event.fields['reason'], 'authorization_revoked')
        for ref in TaskToken.objects.get(run=self.row).scope_refs: self.assertIn(ref, event.scope_refs)
        before = self.snapshot(); self.assertEqual(self.renew().status, 401); self.assertEqual(before, self.snapshot())
    return test

for _mode in ('read', 'write', 'available', 'member', 'provider', 'rebind'):
    setattr(RenewReviewTests, 'test_independent_revocation_' + _mode, revocation_case(_mode))
