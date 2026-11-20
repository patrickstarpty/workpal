from datetime import datetime, timezone
from workpal.agents import service as agents
from workpal.work import service as projects
from workpal.execution.protocol import CapabilityReport
"""Public Interface races using independent real SQLite connections."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from unittest.mock import patch
from django.db import connections
from django.test import TransactionTestCase
from tests import test_runtime_lease_claim as fixtures
from tests.access_support import AccessFixtures
from workpal.agents import runtime_identity as devices
from workpal.agents.models import Agent, RuntimeBinding
from workpal.execution import leases, service as runs
from workpal.execution.models import Run, TaskToken
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import DomainError


class RenewRacesTests(AccessFixtures, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.member.role='owner'; self.member.save()
        self.device=devices.consume_pairing(devices.issue_pairing(self.actor,'Device')['secret'])
        self.project=projects.create(self.actor,'Project')
        self.agent=agents.create(self.actor,'Builder')
        devices.bind(self.actor,self.agent['id'],self.device['runtime_id'],1)
        self.now=datetime(2026,11,20,tzinfo=timezone.utc)
        self.report=CapabilityReport('copilot_cli',1,True,True,True)
    create_run = fixtures.ClaimTests.create_run
    claim = fixtures.ClaimTests.claim
    snapshot = fixtures.ClaimTests.snapshot

    def exercise(self, mode, order):
        row = self.create_run(1)
        with patch.object(leases, '_verify_capabilities', return_value=True), patch.object(leases, '_clock', return_value=self.now):
            lease = self.claim().lease
            other = devices.consume_pairing(devices.issue_pairing(self.actor, 'Other')['secret']) if mode == 'bind' else None
            revision = Agent.objects.get(pk=self.agent['id']).revision
            baseline = (AuditEvent.objects.count(), Outbox.objects.count())
            before_race = self.snapshot()
            barrier, committed = Barrier(2), Event()
            def change(rev):
                if mode == 'cancel':
                    return runs.control(self.actor, row.pk, 'cancel', rev)
                return devices.bind(self.actor, self.agent['id'], other['runtime_id'], rev)
            def worker(which):
                conn = connections['default']
                try:
                    conn.ensure_connection()
                    raw = conn.connection
                    self.assertTrue(Path(conn.settings_dict['NAME']).is_file())
                    barrier.wait(timeout=15)
                    first = (order == 'change' and which == 'change') or (order == 'renew' and which == 'renew')
                    if order != 'race' and not first:
                        self.assertTrue(committed.wait(timeout=15))
                    try:
                        if which == 'renew':
                            value = leases.renew(lease.task_token, run_id=row.pk, epoch=1)
                        else:
                            rev = revision if mode == 'bind' else (3 if order == 'renew' else 2)
                            value = change(rev)
                        return raw, value
                    except DomainError as error:
                        self.assertIn((error.code, error.status), {('revision_conflict', 409), ('storage_busy', 503)})
                        return raw, error
                    finally:
                        if first: committed.set()
                finally:
                    conn.close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker, which) for which in ('change', 'renew')]
                changed, renewed = [f.result(timeout=40) for f in futures]
            self.assertIsNot(changed[0], renewed[0])
            change_result, result = changed[1], renewed[1]
            # Inspect the first pair before any explicit repair/retry can hide a partial write.
            change_committed = not isinstance(change_result, DomainError)
            renew_committed = not isinstance(result, DomainError)
            rotated = renew_committed and result.kind == 'renewed'
            stopped = renew_committed and result.kind == 'stop_only'
            allowed = {Run._meta.label, TaskToken._meta.label, AuditEvent._meta.label, Outbox._meta.label}
            if mode == 'bind' and change_committed:
                allowed.update({Agent._meta.label, RuntimeBinding._meta.label})
            for label, rows in self.snapshot().items():
                if label not in allowed:
                    self.assertEqual(rows, before_race[label], label)
            row.refresh_from_db()
            self.assertEqual(row.revision, 2 + int(renew_committed) + int(mode == 'cancel' and change_committed))
            self.assertEqual(row.status, 'cancel_requested' if stopped or (mode == 'cancel' and change_committed) else 'dispatched')
            self.assertEqual((row.input_snapshot, row.sha256, row.lease_epoch),
                             (before_race[Run._meta.label][0]['input_snapshot'], before_race[Run._meta.label][0]['sha256'], 1))
            self.assertEqual(TaskToken.objects.filter(run=row).count(), 1 + int(rotated))
            self.assertEqual(TaskToken.objects.filter(run=row, revoked_at=None).count(), 0 if stopped else 1)
            self.assertEqual((AuditEvent.objects.count(), Outbox.objects.count()),
                             (baseline[0] + int(renew_committed), baseline[1] + int(renew_committed)))
            if mode == 'bind':
                binding = RuntimeBinding.objects.get(agent_id=self.agent['id'])
                self.assertEqual(Agent.objects.get(pk=self.agent['id']).revision, revision + int(change_committed))
                self.assertEqual(binding.revision, before_race[RuntimeBinding._meta.label][0]['revision'] + int(change_committed))
                self.assertEqual(binding.runtime_id, other['runtime_id'] if change_committed else self.device['runtime_id'])
            # Frozen-input failures remain failures; a later explicit operation is distinct.
            if isinstance(change_result, DomainError):
                before = self.snapshot()
                if change_result.status == 409:
                    with self.assertRaises(DomainError): change(2 if mode == 'cancel' else revision)
                    self.assertEqual(before, self.snapshot())
                change(Run.objects.get(pk=row.pk).revision if mode == 'cancel' else Agent.objects.get(pk=self.agent['id']).revision)
            if isinstance(result, DomainError):
                result = leases.renew(lease.task_token, run_id=row.pk, epoch=1)
            if order == 'change': self.assertEqual(result.kind, 'stop_only')
            if order == 'renew': self.assertEqual(result.kind, 'renewed')
            if result.kind == 'renewed':
                row.refresh_from_db()
                self.assertEqual((row.status, row.revision), ('cancel_requested' if mode == 'cancel' else 'dispatched', 4 if mode == 'cancel' else 3))
                self.assertEqual(TaskToken.objects.filter(run=row, revoked_at=None).count(), 1)
                result = leases.renew(result.lease.task_token, run_id=row.pk, epoch=1)
                reasons = ['renewed', 'stop_observed' if mode == 'cancel' else 'authorization_revoked']
            else:
                reasons = ['stop_observed' if mode == 'cancel' else 'authorization_revoked']
            self.assertEqual(result.kind, 'stop_only')
            self.assertEqual(result.reason, reasons[-1])
            row.refresh_from_db()
            self.assertEqual((row.status, row.revision, row.lease_epoch), ('cancel_requested', 2 + len(reasons) + (mode == 'cancel'), 1))
            self.assertEqual(Run.objects.count(), 1)
            self.assertEqual(TaskToken.objects.filter(run=row, revoked_at=None).count(), 0)
            self.assertCountEqual(list(AuditEvent.objects.filter(action_id='runtime.renew').order_by('pk').values_list('fields', flat=True)), [dict(run_id=row.pk, runtime_id=self.device['runtime_id'], epoch=1, status='dispatched' if reason == 'renewed' else 'cancel_requested', reason=reason) for reason in reasons])
            self.assertEqual((AuditEvent.objects.count(), Outbox.objects.count()), (baseline[0]+len(reasons), baseline[1]+len(reasons)))
            before = self.snapshot()
            self.assertEqual(leases.renew(lease.task_token, run_id=row.pk, epoch=1).status, 401)
            self.assertEqual(before, self.snapshot())

    def test_cancel_race(self): self.exercise('cancel', 'race')
    def test_cancel_commits_first(self): self.exercise('cancel', 'change')
    def test_cancel_after_renew(self): self.exercise('cancel', 'renew')
    def test_bind_race(self): self.exercise('bind', 'race')
    def test_bind_commits_first(self): self.exercise('bind', 'change')
    def test_bind_after_renew(self): self.exercise('bind', 'renew')
