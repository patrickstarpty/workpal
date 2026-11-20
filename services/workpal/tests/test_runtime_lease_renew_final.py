"""Additional renew review; fixture corruption is not a business operation."""
from tests import test_runtime_lease_renew_review as fixture
from unittest.mock import patch
from workpal.execution import leases
from workpal.execution.models import TaskToken
from workpal.contracts import DomainError

class RenewFinalTests(fixture.RenewReviewTests):
    def test_corrupt_scope_container_fails_closed(self):
        from django.db.models import JSONField, Value
        from workpal.execution.models import Run
        token = TaskToken.objects.get(run=self.row)
        original = token.scope_refs
        for scope in (None, {}, [], '', 42, True):
            for status in ('dispatched', 'cancel_requested'):
                with self.subTest(scope=scope, status=status):
                    TaskToken.objects.filter(pk=token.pk).update(scope_refs=Value(scope, output_field=JSONField()))
                    Run.objects.filter(pk=self.row.pk).update(status=status)
                    before = self.snapshot()
                    with self.assertRaises(DomainError) as caught:
                        self.renew()
                    self.assertEqual((caught.exception.code, caught.exception.status), ('storage_unavailable', 503))
                    self.assertEqual(before, self.snapshot())
        TaskToken.objects.filter(pk=token.pk).update(scope_refs=original)
        Run.objects.filter(pk=self.row.pk).update(status='dispatched')
        self.assertEqual(self.renew().kind, 'renewed')

for name in dir(fixture.RenewReviewTests):
    if name.startswith('test_'):
        setattr(RenewFinalTests, name, None)

def exception_case(code, status):
    def test(self):
        before = self.snapshot()
        with patch.object(leases, '_claim_refs', side_effect=DomainError(code, 'Unavailable', status=status)):
            with self.assertRaises(DomainError) as caught:
                self.renew()
        self.assertEqual((caught.exception.code, caught.exception.status), (code, status))
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.renew().kind, 'renewed')
    return test

for code, status in [('storage_unavailable',503), ('unexpected',403),
                     ('permission_denied',401), ('authentication_required',404),
                     ('not_found',401)]:
    setattr(RenewFinalTests, 'test_authorization_exception_%s_%s' % (code,status), exception_case(code,status))
