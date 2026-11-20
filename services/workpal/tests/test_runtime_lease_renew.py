from tests import test_runtime_lease_claim as fixtures
from unittest.mock import patch
from datetime import timedelta
from workpal.execution import leases, service as runs
from workpal.execution.models import TaskToken

class RenewTests(fixtures.ClaimTests):
    test_default_and_strict_reports = None
    test_claim_identity_and_no_redispatch = None
    test_persistent_scan_skips_denied_sources = None

    def test_rotation(self):
        row = self.create_run(1)
        with patch.object(leases, '_verify_capabilities', return_value=True), patch.object(leases, '_clock', return_value=self.now):
            lease = self.claim().lease
            result = leases.renew(lease.task_token, run_id=row.pk, epoch=1)
            self.assertEqual(result.kind, 'renewed')
            self.assertEqual(result.lease.expires_at, self.now + timedelta(seconds=45))
            self.assertEqual(TaskToken.objects.filter(revoked_at=None).count(), 1)
            self.assertEqual(leases.renew(lease.task_token, run_id=row.pk, epoch=1).status, 401)

    def test_denied_priority_zero_writes(self):
        row = self.create_run(1)
        with patch.object(leases, '_verify_capabilities', return_value=True), patch.object(leases, '_clock', return_value=self.now):
            lease = self.claim().lease
            for status in ['completed', 'failed', 'cancelled', 'awaiting_input']:
                type(row).objects.filter(pk=row.pk).update(status=status, lease_expires_at=self.now)
                for secret, rid, epoch, expected in [('bad', row.pk+1, 2,401),(lease.task_token,row.pk+1,2,404),(lease.task_token,row.pk,2,409),(lease.task_token,row.pk,1,409)]:
                    before=self.snapshot()
                    self.assertEqual(leases.renew(secret,run_id=rid,epoch=epoch).status,expected)
                    self.assertEqual(before,self.snapshot())

    def test_stop_once(self):
        for n, status in enumerate(['cancel_requested','recovery_required','dispatched']):
            row=self.create_run(n)
            with patch.object(leases,'_verify_capabilities',return_value=True), patch.object(leases,'_clock',return_value=self.now):
                lease=self.claim().lease
                type(row).objects.filter(pk=row.pk).update(status=status,lease_expires_at=self.now)
                result=leases.renew(lease.task_token,run_id=row.pk,epoch=1)
                self.assertEqual(result.reason,'lease_expired' if status=='dispatched' else 'stop_observed')
                before=self.snapshot()
                self.assertEqual(leases.renew(lease.task_token,run_id=row.pk,epoch=1).status,401)
                self.assertEqual(before,self.snapshot())
            type(row).objects.filter(pk=row.pk).update(status='cancelled')

    def test_revocation_and_record_rollback(self):
        from workpal.contracts import DomainError
        for n, mode in enumerate(['member','source','binding','capability']):
            row=self.create_run(n)
            with patch.object(leases,'_verify_capabilities',return_value=True), patch.object(leases,'_clock',return_value=self.now):
                lease=self.claim().lease
            if mode=='member':
                self.member.delete()
            elif mode=='source':
                self.register(self.workspace.pk, runs.ref(row.pk), [self.a])
                from workpal.access.models import RegisteredObject
                RegisteredObject.objects.filter(kind=self.a.kind,object_id=self.a.id).update(available=False)
            elif mode=='binding':
                from workpal.agents.models import RuntimeBinding
                RuntimeBinding.objects.filter(agent_id=self.agent['id']).update(enabled=False)
            original=leases.audit.record
            def fail(*args, **kwargs):
                original(*args, **kwargs)
                raise DomainError('storage_unavailable','Unavailable',status=503)
            with patch.object(leases,'_clock',return_value=self.now), patch.object(leases,'_verify_capabilities',return_value=mode!='capability'):
                before=self.snapshot()
                with patch.object(leases.audit,'record',side_effect=fail), self.assertRaises(DomainError):
                    leases.renew(lease.task_token,run_id=row.pk,epoch=1)
                self.assertEqual(before,self.snapshot())
                result=leases.renew(lease.task_token,run_id=row.pk,epoch=1)
                self.assertEqual(result.reason,'authorization_revoked')
            # Each revocation uses a fresh real fixture for the next independent case.
            if n<3:
                self._fixture_teardown()
                self._fixture_setup()
                self.setUp()
