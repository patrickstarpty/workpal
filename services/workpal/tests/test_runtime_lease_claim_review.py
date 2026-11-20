"""Independent claim transaction and current-authorization review evidence."""
from tests import test_runtime_lease_claim as fixtures
from unittest.mock import patch
from dataclasses import asdict
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from django.db import connections
from django.contrib.auth import get_user_model
from workpal.contracts import Actor, DomainError
from workpal.identity.models import Membership
from workpal.access.models import SourceGrant
from workpal.execution import leases
from workpal.execution.models import Run, TaskToken, RuntimeClaimScan
from workpal.agents.models import RuntimeBinding, Agent, Runtime
from workpal.agents import runtime_identity as devices
from workpal.audit import service as audit
from workpal.audit.models import AuditEvent, Outbox

class ReviewTests(fixtures.ClaimTests):
    # Inherit fixtures, not the three previously accepted test methods.
    test_default_and_strict_reports = None
    test_claim_identity_and_no_redispatch = None
    test_persistent_scan_skips_denied_sources = None

    def setUp(self):
        super().setUp()
        admin=get_user_model().objects.create(username='pair-admin')
        Membership.objects.create(user=admin,workspace=self.workspace,role='owner')
        self.admin=Actor(admin.pk,self.workspace.pk)
        self.device=devices.consume_pairing(devices.issue_pairing(self.admin,'Independent device')['secret'])
        devices.bind(self.admin,self.agent['id'],self.device['runtime_id'],Agent.objects.get(pk=self.agent["id"]).revision)

    def denied_scan(self):
        before=self.snapshot()
        with patch.object(leases,'_verify_capabilities',return_value=True):
            self.assertEqual(asdict(self.claim()),{'lease':None})
        after=self.snapshot()
        before.pop('execution.RuntimeClaimScan'); after.pop('execution.RuntimeClaimScan')
        self.assertEqual(before,after)

    def test_creator_membership_current_not_pair_admin(self):
        self.create_run(1)
        self.member.delete()
        self.denied_scan()

    def test_independent_agent_source_requires_write(self):
        self.create_run(1)
        from workpal.agents import service as agents
        self.register(self.workspace.pk,agents.ref(self.agent['id']),[self.a])
        self.grant(self.a,read=True)
        self.denied_scan()
        SourceGrant.objects.filter(user=self.user).update(write=True)
        with patch.object(leases,'_verify_capabilities',return_value=True):
            self.assertIsNotNone(self.claim().lease)

    def test_real_record_then_failure_rolls_back_every_table(self):
        self.create_run(1)
        before=self.snapshot(); original=audit.record
        def fail(*a,**kw):
            original(*a,**kw)
            raise DomainError('storage_unavailable','Unavailable.',status=503)
        with patch.object(leases,'_verify_capabilities',return_value=True), patch.object(audit,'record',side_effect=fail):
            with self.assertRaises(DomainError) as caught: self.claim()
            self.assertEqual(caught.exception.status,503)
        self.assertEqual(before,self.snapshot())
        with patch.object(leases,'_verify_capabilities',return_value=True):
            result=self.claim().lease
        self.assertIsNotNone(result)
        from django.core.cache import cache
        payload=repr(list(AuditEvent.objects.values()))+repr(list(Outbox.objects.values()))+repr(getattr(cache,'_cache',{}))
        token=TaskToken.objects.get()
        for value in (result.task_token,token.secret_hash): self.assertNotIn(value,payload)

    def test_verifier_errors_and_overflows_are_zero_write(self):
        row=self.create_run(1)
        for response in (DomainError('storage_unavailable','Unavailable.',status=503),1,None):
            before=self.snapshot()
            kwargs={'side_effect':response} if isinstance(response,Exception) else {'return_value':response}
            with patch.object(leases,'_verify_capabilities',**kwargs):
                with self.assertRaises(DomainError) as caught: self.claim()
            self.assertEqual(caught.exception.status,503 if isinstance(response,Exception) else 400)
            self.assertEqual(before,self.snapshot())
        with patch.object(leases,'_verify_capabilities',return_value=True):
            for now in (datetime.max.replace(tzinfo=timezone.utc),datetime(2026,1,1)):
                before=self.snapshot()
                with patch.object(leases,'_clock',return_value=now):
                    with self.assertRaises(DomainError): leases.claim(self.device['runtime_token'],self.report)
                self.assertEqual(before,self.snapshot())
            Run.objects.filter(pk=row.pk).update(revision=2**31-1)
            before=self.snapshot()
            with self.assertRaises(DomainError): self.claim()
            self.assertEqual(before,self.snapshot())
            Run.objects.filter(pk=row.pk).update(revision=1)
            RuntimeClaimScan.objects.create(runtime_id=self.device['runtime_id'],revision=2**63-1)
            before=self.snapshot()
            with self.assertRaises(DomainError): self.claim()
            self.assertEqual(before,self.snapshot())

    def test_candidate_verifier_failure_rolls_back_scan_and_preserves_errors(self):
        row = self.create_run(1)
        for value in (DomainError('storage_unavailable', 'Unavailable.', status=503),
                      'private-verifier-result', None):
            before = self.snapshot()
            def verify(**kwargs):
                if kwargs['agent_id'] == 0:
                    return True
                if isinstance(value, Exception):
                    raise value
                return value
            with patch.object(leases, '_verify_capabilities', side_effect=verify) as verifier:
                with self.assertRaises(DomainError) as caught:
                    self.claim()
            self.assertEqual([call.kwargs['agent_id'] for call in verifier.call_args_list],
                             [0, self.agent['id']])
            expected = ('storage_unavailable', 503) if isinstance(value, Exception) else ('invalid_input', 400)
            self.assertEqual((caught.exception.code, caught.exception.status), expected)
            self.assertNotIn('private-verifier-result', str(caught.exception))
            self.assertEqual(before, self.snapshot())
        with patch.object(leases, '_verify_capabilities',
                          side_effect=lambda **kw: kw['agent_id'] == 0):
            self.assertEqual(asdict(self.claim()), {'lease': None})
        self.assertEqual(TaskToken.objects.count(), 0)
        with patch.object(leases, '_verify_capabilities', return_value=True):
            self.assertEqual(self.claim().lease.run_id, row.pk)

    def test_claim_secrets_and_input_body_do_not_enter_audit_cache_or_errors(self):
        import io
        import logging
        from contextlib import redirect_stdout, redirect_stderr
        from workpal.actions.models import IdempotencyResult
        from workpal.execution.protocol import CapabilityReport
        from django.core.cache import cache
        marker = 'private-requirement-body-claim-review'
        row = self.create_run(marker)
        before_cache = list(IdempotencyResult.objects.order_by('pk').values())
        before_local = dict(getattr(cache, '_cache', {}))
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        logger = logging.getLogger()
        logger.addHandler(handler)
        try:
            with redirect_stdout(output), redirect_stderr(output):
                with patch.object(leases, '_verify_capabilities', return_value=True):
                    lease = self.claim().lease
                errors = []
                for secret, report in (
                    ('invalid-' + marker, self.report),
                    (self.device['runtime_token'], CapabilityReport(marker, 1, True, True, True)),
                    (lease.task_token, self.report),
                ):
                    with self.assertRaises(DomainError) as caught:
                        leases.claim(secret, report)
                    errors.append(vars(caught.exception))
        finally:
            logger.removeHandler(handler)
        self.assertIn(marker, repr(lease.input_snapshot))
        self.assertEqual(before_cache, list(IdempotencyResult.objects.order_by('pk').values()))
        self.assertEqual(before_local, dict(getattr(cache, '_cache', {})))
        token = TaskToken.objects.get(run=row)
        event = AuditEvent.objects.get(action_id='runtime.claim')
        emitted = repr(list(AuditEvent.objects.filter(pk=event.pk).values()))
        emitted += repr(list(Outbox.objects.filter(event=event).values()))
        emitted += repr(errors) + output.getvalue()
        for value in (marker, self.device['runtime_token'], lease.task_token, token.secret_hash):
            self.assertNotIn(value, emitted)

    def test_two_file_connections_single_dispatch(self):
        row=self.create_run(1); barrier=Barrier(2)
        baseline=AuditEvent.objects.filter(action_id='runtime.claim').count()
        def worker():
            c=connections['default']
            try:
                c.ensure_connection(); raw=c.connection
                self.assertTrue(Path(c.settings_dict['NAME']).is_file())
                barrier.wait(timeout=15)
                try: result=self.claim()
                except DomainError as e:
                    self.assertEqual((e.code,e.status),('storage_busy',503))
                    result=self.claim()
                return raw,result
            finally: c.close()
        with patch.object(leases,'_verify_capabilities',return_value=True):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(worker) for _ in range(2)]
                results=[f.result(timeout=30) for f in futures]
            self.assertIsNone(self.claim().lease)
        self.assertIsNot(results[0][0],results[1][0])
        self.assertEqual(sum(r.lease is not None for _,r in results),1)
        row.refresh_from_db(); self.assertEqual((row.status,row.lease_epoch),('dispatched',1))
        self.assertEqual(TaskToken.objects.filter(run=row,revoked_at=None).count(),1)
        self.assertEqual(AuditEvent.objects.filter(action_id='runtime.claim').count(),baseline+1)
        self.assertEqual(Outbox.objects.filter(event__action_id='runtime.claim').count(),1)
        self.assertEqual(RuntimeClaimScan.objects.get().last_pk,0)

    def test_new_and_historical_resource_restrictions(self):
        from workpal.work import resources
        row=self.create_run(1); original=(row.input_snapshot,row.sha256)
        grant=self.grant(self.a,read=True,write=True)
        resource=resources.create(self.actor,self.project['id'],'Repo','github','org/repo',source_refs=[asdict(self.a)])
        grant.write=False; grant.save()
        self.denied_scan()
        SourceGrant.objects.filter(user=self.user).update(write=True)
        with patch.object(leases,'_verify_capabilities',return_value=True): self.assertIsNotNone(self.claim().lease)
        row.refresh_from_db(); self.assertEqual((row.input_snapshot,row.sha256),original)
        historical=self.create_run(2)
        resources.set_archived(self.actor,self.project['id'],resource['id'],resource['revision'],True)
        SourceGrant.objects.filter(user=self.user).update(write=False)
        self.denied_scan()

    def test_saved_requirements_source_requires_write(self):
        from workpal.work import issues
        row=self.create_run(1)
        self.register(self.workspace.pk,issues.requirement_ref(row.requirements_id),[self.a])
        self.grant(self.a,read=True)
        self.denied_scan()

    def test_unbound_and_current_provider_candidates_are_hidden(self):
        from workpal.agents.models import Agent
        self.create_run(1)
        RuntimeBinding.objects.filter(agent_id=self.agent['id']).update(enabled=False)
        self.denied_scan()
        RuntimeBinding.objects.filter(agent_id=self.agent['id']).update(enabled=True)
        Agent.objects.filter(pk=self.agent['id']).update(provider_key='codex_cli')
        self.denied_scan()

    def test_rebound_and_revoked_device(self):
        self.create_run(1)
        alternate=devices.consume_pairing(devices.issue_pairing(self.admin,'Replacement')['secret'])
        devices.bind(self.admin,self.agent['id'],alternate['runtime_id'],Agent.objects.get(pk=self.agent['id']).revision)
        self.denied_scan()
        Runtime.objects.filter(pk=self.device['runtime_id']).update(revoked_at=self.now)
        before=self.snapshot()
        with patch.object(leases,'_verify_capabilities',return_value=True):
            with self.assertRaises(DomainError) as caught: self.claim()
        self.assertEqual(caught.exception.status,401)
        self.assertEqual(before,self.snapshot())

from django.test import SimpleTestCase
import os
import sys
import subprocess
import tempfile

class HistoricalLeaseUpgrade(SimpleTestCase):
    def test_real_execution_0002_upgrade(self):
        script=r'''
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
ex=MigrationExecutor(connection)
leaves=ex.loader.graph.leaf_nodes()
old=[x for x in leaves if x[0]!='execution']+[('execution','0002_remove_run_one_active_manual_run_and_more')]
ex.migrate(old)
a=ex.loader.project_state(old).apps
U=a.get_model('auth','User'); W=a.get_model('identity','Workspace')
P=a.get_model('work','Project'); I=a.get_model('work','Issue'); Q=a.get_model('work','IssueRequirements')
A=a.get_model('agents','Agent'); R=a.get_model('execution','Run'); N=a.get_model('execution','Intent')
u=U.objects.create(username='legacy'); w=W.objects.create(name='legacy'); p=P.objects.create(workspace=w,name='legacy')
i=I.objects.create(workspace=w,project=p,created_by=u,status_key='todo',workflow_snapshot={})
q=Q.objects.create(issue=i,number=1,title='历史',description='private legacy body',sha256='a'*64,created_by=u)
i.current_requirements=q;i.save()
ag=A.objects.create(workspace=w,created_by=u,name='legacy')
r=R.objects.create(workspace=w,created_by=u,issue=i,requirements=q,project=p,agent=ag,input_snapshot={'private':'历史'},sha256='b'*64)
N.objects.create(workspace=w,actor=u,key='legacy',digest='c'*64,run=r)
tables=[t for t in connection.introspection.table_names() if t.startswith(('execution_','work_','agents_'))]
with connection.cursor() as c:
    columns={t:[x.name for x in connection.introspection.get_table_description(c,t)] for t in tables}
def rows():
    with connection.cursor() as c:
        return {t:c.execute('SELECT '+','.join('"'+x+'"' for x in columns[t])+' FROM "'+t+'" ORDER BY 1').fetchall() for t in tables}
before=rows()
for _ in range(2):
    MigrationExecutor(connection).migrate(leaves)
    assert rows()==before
    with connection.cursor() as c:
        assert c.execute('SELECT lease_owner_id,lease_expires_at,lease_epoch FROM execution_run').fetchall()==[(None,None,0)]
        assert c.execute('SELECT COUNT(*) FROM execution_tasktoken').fetchone()==(0,)
        assert c.execute('SELECT COUNT(*) FROM execution_runtimeclaimscan').fetchone()==(0,)
connection.close()
'''
        with tempfile.TemporaryDirectory(prefix='workpal-lease-history-') as directory:
            result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],env={**os.environ,'DJANGO_SETTINGS_MODULE':'config.settings','WORKPAL_DB_PATH':str(Path(directory)/'old.sqlite3')},capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
