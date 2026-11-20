from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from django.apps import apps
from django.test import TransactionTestCase
from django.db import connection
from tests.access_support import AccessFixtures
from workpal.agents import runtime_identity as devices, service as agents
from workpal.execution import leases, service as runs
from workpal.execution.protocol import CapabilityReport
from workpal.execution.models import Run, TaskToken
from workpal.work import service as projects, issues
from workpal.contracts import DomainError

class ClaimTests(AccessFixtures, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.member.role='owner'; self.member.save()
        self.device=devices.consume_pairing(devices.issue_pairing(self.actor,'Device')['secret'])
        self.project=projects.create(self.actor,'Project')
        self.agent=agents.create(self.actor,'Builder')
        devices.bind(self.actor,self.agent['id'],self.device['runtime_id'],1)
        self.now=datetime(2026,11,20,tzinfo=timezone.utc)
        self.report=CapabilityReport('copilot_cli',1,True,True,True)
    def create_run(self, n):
        issue=issues.create(self.actor,self.project['id'],str(n))
        return Run.objects.get(pk=runs.start(self.actor,{'type':'issue','id':issue['id']},self.agent['id'],str(n))['id'])
    def snapshot(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()}
    def claim(self):
        with patch.object(leases,'_clock',return_value=self.now):
            return leases.claim(self.device['runtime_token'],self.report)
    def test_default_and_strict_reports(self):
        self.create_run(0)
        before=self.snapshot()
        reports=[self.report,{},CapabilityReport('unknown',1,True,True,True),CapabilityReport('copilot_cli',True,True,True,True),CapabilityReport('copilot_cli',1,1,True,True)]
        reports += [CapabilityReport(p,1,True,True,True) for p in ['codex_cli','claude_code','gemini_cli','opencode']]
        for report in reports:
            with self.assertRaises(DomainError): leases.claim(self.device['runtime_token'],report)
            self.assertEqual(before,self.snapshot())
    def test_claim_identity_and_no_redispatch(self):
        row=self.create_run(0); snapshot=row.input_snapshot; digest=row.sha256
        with patch.object(leases,'_verify_capabilities',return_value=True) as verify:
            lease=self.claim().lease
            self.assertEqual([c.kwargs['agent_id'] for c in verify.call_args_list],[0,self.agent['id']])
            self.assertIsNone(self.claim().lease)
        row.refresh_from_db()
        self.assertEqual((row.status,row.lease_epoch,row.revision),('dispatched',1,2))
        self.assertEqual(row.lease_expires_at,self.now+timedelta(seconds=45))
        self.assertEqual((row.input_snapshot,row.sha256),(snapshot,digest))
        token=TaskToken.objects.get(run=row)
        self.assertEqual(token.expires_at,self.now+timedelta(seconds=60))
        with patch.object(leases,'_clock',return_value=self.now):
            self.assertEqual(leases.authenticate_task(lease.task_token).run_id,row.pk)
        from workpal.audit.models import AuditEvent, Outbox
        event=AuditEvent.objects.get(action_id='runtime.claim')
        self.assertEqual(event.outcome,'completed')
        self.assertEqual(event.fields,dict(run_id=row.pk,runtime_id=self.device['runtime_id'],epoch=1,status='dispatched',reason='claimed'))
        self.assertTrue(Outbox.objects.filter(event=event).exists())
        self.assertEqual(event.scope_refs,token.scope_refs)
        self.assertNotIn(lease.task_token,repr(event.fields))
        self.assertEqual(lease.allowed_actions,())
        lease.input_snapshot.clear(); row.refresh_from_db(); self.assertEqual(row.input_snapshot,snapshot)
    def test_persistent_scan_skips_denied_sources(self):
        denied=[self.create_run(n) for n in range(32)]
        target=self.create_run(33)
        # An unavailable historical root makes the real access Interface reject each candidate.
        from workpal.access.models import RegisteredObject
        for row in denied:
            self.register(self.workspace.pk,runs.ref(row.pk),[self.a])
        RegisteredObject.objects.filter(kind='source',object_id='a',workspace=self.workspace).update(available=False)
        with patch.object(leases,'_verify_capabilities',return_value=True):
            self.assertEqual(asdict(self.claim()),{'lease':None})
            connection.close()
            self.assertEqual(self.claim().lease.run_id,target.pk)
        self.assertEqual(TaskToken.objects.count(),1)
