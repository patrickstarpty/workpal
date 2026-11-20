"""ORM token fixtures are not production issuance or claim verification."""
import hashlib
from dataclasses import FrozenInstanceError, asdict
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from django.apps import apps
from django.db import IntegrityError, transaction
from django.test import TestCase
from tests.access_support import AccessFixtures
from workpal.agents import runtime_identity as devices, service as agents
from workpal.agents.models import Runtime
from workpal.execution import leases, protocol, service as runs
from workpal.execution.models import Run, TaskToken
from workpal.work import service as projects, issues
from workpal.contracts import DomainError

class TaskIdentityTests(AccessFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.member.role='owner'; self.member.save()
        pairing=devices.issue_pairing(self.actor,'Device')
        self.pair_secret=pairing['secret']
        self.device=devices.consume_pairing(self.pair_secret)
        project=projects.create(self.actor,'Project')
        issue=issues.create(self.actor,project['id'],'Task')
        agent=agents.create(self.actor,'Builder')
        self.run=Run.objects.get(pk=runs.start(self.actor,{'type':'issue','id':issue['id']},agent['id'],'start')['id'])
        self.now=datetime(2026,11,20,tzinfo=timezone.utc)
        self.secret='wp_task_'+'a'*64
        self.token=TaskToken.objects.create(run=self.run,runtime_id=self.device['runtime_id'],epoch=1,secret_hash=hashlib.sha256(self.secret.encode()).hexdigest(),expires_at=self.now+timedelta(seconds=60))

    def snapshot(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()}

    def identify(self, secret=None):
        before=self.snapshot()
        try:
            with patch.object(leases,'_clock',return_value=self.now):
                return leases.authenticate_task(self.secret if secret is None else secret)
        finally:
            self.assertEqual(before,self.snapshot())

    def denied(self,secret,status=401):
        with self.assertRaises(DomainError) as error: self.identify(secret)
        self.assertEqual(error.exception.status,status)
        if status==401: self.assertEqual(error.exception.code,'authentication_required')
        self.assertNotIn(self.secret,str(error.exception))

    def test_identity_and_frozen_contracts(self):
        identity=self.identify()
        self.assertEqual(asdict(identity),dict(runtime_id=self.device['runtime_id'],workspace_id=self.workspace.pk,run_id=self.run.pk,epoch=1,token_id=self.token.pk))
        values=[identity,protocol.CapabilityReport('copilot_cli',1,True,True,True),protocol.Lease(1,1,self.now,{},self.secret),protocol.Renewal(1,1,self.now,self.secret),protocol.Renewed(protocol.Renewal(1,1,self.now,self.secret)),protocol.StopOnly(1,1,'stop_observed'),protocol.Denied('x',409),protocol.ClaimResult(None)]
        for value in values:
            with self.assertRaises(FrozenInstanceError): value.extra=1
        self.assertEqual(values[2].allowed_actions,())
        self.assertNotIn('secret',repr(identity)); self.assertNotIn('hash',repr(identity))
        with self.assertRaises(TypeError): protocol.Denied('x',409,kind='other')

    def test_invalid_credentials(self):
        for secret in [False,1,b'bytes','',self.secret+' ',self.secret.upper(),'wp_task_'+'b'*64,self.pair_secret,self.device['runtime_token']]:
            self.denied(secret)
        self.denied(None if False else ' wp_task_'+'a'*64)
        with self.assertRaises(DomainError): leases.authenticate_task(None)

    def test_expiry_revocations_and_clock(self):
        TaskToken.objects.filter(pk=self.token.pk).update(expires_at=self.now)
        self.denied(self.secret)
        TaskToken.objects.filter(pk=self.token.pk).update(expires_at=self.now+timedelta(seconds=60),revoked_at=self.now)
        self.denied(self.secret)
        TaskToken.objects.filter(pk=self.token.pk).update(revoked_at=None)
        Runtime.objects.filter(pk=self.device['runtime_id']).update(revoked_at=self.now)
        self.denied(self.secret)
        for clock in [None,datetime(2026,1,1),self.now.astimezone(timezone(timedelta(hours=1)))]:
            before=self.snapshot()
            with patch.object(leases,'_clock',return_value=clock):
                with self.assertRaises(DomainError) as error: leases.authenticate_task(self.secret)
            self.assertEqual(error.exception.status,400); self.assertEqual(before,self.snapshot())

    def test_identity_is_not_permission(self):
        devices.bind(self.actor,self.run.agent_id,self.device['runtime_id'],1)
        devices.unbind(self.actor,self.run.agent_id,2)
        self.member.delete()
        Run.objects.filter(pk=self.run.pk).update(status='cancelled',lease_epoch=99,lease_expires_at=self.now)
        self.assertEqual(self.identify().epoch,1)
        self.denied('wp_task_'+'b'*64)

    def test_defaults_and_live_token_constraint(self):
        self.assertEqual((self.run.lease_owner_id,self.run.lease_epoch,self.run.lease_expires_at),(None,0,None))
        self.assertEqual(self.token.scope_refs,[])
        fields=dict(run=self.run,runtime_id=self.device['runtime_id'],epoch=2,secret_hash='b'*64,expires_at=self.now)
        with self.assertRaises(IntegrityError),transaction.atomic(): TaskToken.objects.create(**fields)
        TaskToken.objects.filter(pk=self.token.pk).update(revoked_at=self.now)
        TaskToken.objects.create(**fields)
        with self.assertRaises(IntegrityError),transaction.atomic(): TaskToken.objects.create(**fields)
