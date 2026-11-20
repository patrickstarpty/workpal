"""Remaining public renew scope and output checks; no inherited test discovery."""
from dataclasses import asdict
from unittest.mock import patch
import logging
import hashlib
from django.test import TransactionTestCase
from tests import test_runtime_lease_renew_review as fixture
from workpal.execution import leases
from workpal.execution.models import Run, TaskToken
from workpal.contracts import DomainError, ObjectRef
from workpal.audit.models import AuditEvent, Outbox

from tests.access_support import AccessFixtures

class ScopeOutputTests(AccessFixtures, TransactionTestCase):
    create_run = fixture.fixtures.ClaimTests.create_run
    snapshot = fixture.fixtures.ClaimTests.snapshot
    claim = fixture.fixtures.ClaimTests.claim
    renew = fixture.RenewReviewTests.renew
    # Compose fixture setup explicitly rather than inherit its test methods.
    def setUp(self):
        from workpal.agents import runtime_identity as devices, service as agents
        from workpal.work import service as projects
        from workpal.execution.protocol import CapabilityReport
        from datetime import datetime, timezone
        super().setUp()
        self.member.role='owner'; self.member.save()
        self.device=devices.consume_pairing(devices.issue_pairing(self.actor,'Device')['secret'])
        self.project=projects.create(self.actor,'Project')
        self.agent=agents.create(self.actor,'Builder')
        devices.bind(self.actor,self.agent['id'],self.device['runtime_id'],1)
        self.now=datetime(2026,11,20,tzinfo=timezone.utc)
        self.report=CapabilityReport('copilot_cli',1,True,True,True)
        self.row = self.create_run('unique-scope-output-private-body')
        for name, value in (('_clock', self.now), ('_verify_capabilities', True)):
            p = patch.object(leases, name, return_value=value)
            p.start(); self.addCleanup(p.stop)
        self.lease = self.claim().lease

    def test_added_resource_authorization_and_saved_append_stop(self):
        from workpal.work import resources
        from workpal.access.models import SourceGrant
        from workpal.agents import service as agents
        before_input = (self.row.input_snapshot, self.row.sha256)
        old = TaskToken.objects.get(run=self.row).scope_refs
        self.grant(self.a, read=True, write=True)
        resource = resources.create(self.actor,self.project['id'],'Repo','github','org/repo',source_refs=[asdict(self.a)])
        result = self.renew()
        scope = TaskToken.objects.get(run=self.row, revoked_at=None).scope_refs
        for ref in old + [asdict(self.a), asdict(resources.ref(resource['id']))]: self.assertIn(ref, scope)
        self.lease = result.lease
        self.register(self.workspace.pk, agents.ref(self.agent['id']), [self.b])
        self.grant(self.b, read=True, write=True)
        SourceGrant.objects.filter(user=self.user).update(write=False)
        # Exercise current source permissions with an ordinary member.
        self.member.role='member'; self.member.save()
        result = self.renew()
        self.assertEqual(result.reason, 'authorization_revoked')
        event = AuditEvent.objects.get(action_id='runtime.renew', fields__reason='authorization_revoked')
        for ref in scope + [asdict(self.b)]: self.assertIn(ref, event.scope_refs)
        self.row.refresh_from_db()
        self.assertEqual(before_input,(self.row.input_snapshot,self.row.sha256))

    def test_new_unsaved_resource_denies_without_inventing_stop_roots(self):
        from workpal.work import resources
        from workpal.access.models import SourceGrant
        self.grant(self.a, read=True, write=True)
        resources.create(self.actor,self.project['id'],'Restricted','github','org/private',source_refs=[asdict(self.a)])
        SourceGrant.objects.filter(user=self.user).update(write=False)
        old=TaskToken.objects.get(run=self.row).scope_refs
        original=(self.row.input_snapshot,self.row.sha256)
        self.assertEqual(self.renew().reason,'authorization_revoked')
        event=AuditEvent.objects.get(action_id='runtime.renew')
        for ref in old: self.assertIn(ref,event.scope_refs)
        self.assertNotIn(asdict(self.a),event.scope_refs)
        self.row.refresh_from_db()
        self.assertEqual(original,(self.row.input_snapshot,self.row.sha256))

    def test_cross_workspace_scope_rolls_back_both_paths_and_retry(self):
        foreign = self.register(self.other.pk,ObjectRef('source','foreign'),is_source=True)
        token=TaskToken.objects.get(run=self.row); original=token.scope_refs
        for status in ('dispatched','cancel_requested'):
            TaskToken.objects.filter(pk=token.pk).update(scope_refs=original+[asdict(foreign)])
            Run.objects.filter(pk=self.row.pk).update(status=status)
            before=self.snapshot()
            with self.assertRaises(DomainError) as caught: self.renew()
            self.assertEqual(caught.exception.status,503)
            self.assertEqual(before,self.snapshot())
        TaskToken.objects.filter(pk=token.pk).update(scope_refs=original)
        Run.objects.filter(pk=self.row.pk).update(status='dispatched')
        self.assertEqual(self.renew().kind,'renewed')

    def test_output_failure_and_cache_matrix(self):
        from django.core.cache import cache
        from workpal.actions.models import IdempotencyResult
        captured=[]
        class Capture(logging.Handler):
            def emit(self, record): captured.append(record.getMessage())
        handler=Capture(); logging.getLogger().addHandler(handler)
        self.addCleanup(logging.getLogger().removeHandler,handler)
        cache_before=(list(IdempotencyResult.objects.values()),dict(getattr(cache,'_cache',{})))
        outputs=[]
        old_secret=self.lease.task_token
        original=leases.audit.record
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise DomainError('storage_unavailable','Unavailable',status=503)
        for status in ('dispatched','cancel_requested'):
            Run.objects.filter(pk=self.row.pk).update(status=status)
            before=self.snapshot()
            with patch.object(leases.audit,'record',side_effect=fail):
                with self.assertRaises(DomainError) as error: self.renew()
            self.assertEqual(error.exception.status,503); outputs.append(str(error.exception))
            self.assertEqual(before,self.snapshot())
        Run.objects.filter(pk=self.row.pk).update(status='dispatched')
        before=self.snapshot()
        outputs.append(asdict(self.renew(secret='bad')))
        with self.assertRaises(DomainError) as error: self.renew(epoch=True)
        self.assertEqual(error.exception.status,400); outputs.append(str(error.exception))
        self.assertEqual(before,self.snapshot())
        result=self.renew(); new_secret=result.lease.task_token
        public=asdict(result); self.assertEqual(public['lease'].pop('task_token'),new_secret)
        outputs.append(public); self.lease=result.lease
        Run.objects.filter(pk=self.row.pk).update(status='cancel_requested')
        outputs.append(asdict(self.renew()))
        self.assertEqual(AuditEvent.objects.filter(action_id='runtime.renew').count(),2)
        self.assertEqual(Outbox.objects.filter(event__action_id='runtime.renew').count(),2)
        self.assertEqual(cache_before,(list(IdempotencyResult.objects.values()),dict(getattr(cache,'_cache',{}))))
        for reason, status in (('renewed','dispatched'), ('stop_observed','cancel_requested')):
            event=AuditEvent.objects.get(action_id='runtime.renew', fields__reason=reason)
            self.assertEqual(event.fields,dict(run_id=self.row.pk,runtime_id=self.device['runtime_id'],epoch=1,status=status,reason=reason))
            self.assertEqual(event.outcome,'completed')
            self.assertEqual(Outbox.objects.filter(event=event).count(),1)
        emitted=repr(outputs)+repr(list(AuditEvent.objects.values()))+repr(list(Outbox.objects.values()))+repr(cache_before)+repr(captured)
        for secret in [hashlib.sha256(self.device['runtime_token'].encode()).hexdigest(),old_secret,new_secret,self.device['runtime_token'],'unique-scope-output-private-body',self.row.sha256]+list(TaskToken.objects.values_list('secret_hash',flat=True)):
            self.assertNotIn(secret,emitted)
