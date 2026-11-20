from datetime import timedelta
from unittest.mock import patch
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership
from workpal.contracts import Actor, DomainError
from workpal.agents import runtime_identity as core
from workpal.agents.models import Runtime, RuntimePairing
from workpal.audit.models import AuditEvent, Outbox
from workpal.access.models import RegisteredObject

class RuntimePairingTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username='pair-admin')
        self.workspace = Workspace.objects.create(name='Pair')
        self.member = Membership.objects.create(user=self.user, workspace=self.workspace, role='owner')
        self.actor = Actor(self.user.pk, self.workspace.pk)

    def pair(self):
        issued = core.issue_pairing(self.actor, 'Fixed name')
        return issued, core.consume_pairing(issued['secret'])

    def test_core_response_loss_and_revoke(self):
        issued, result = self.pair()
        self.assertEqual(core.authenticate_runtime(result['runtime_token']).runtime_id, result['runtime_id'])
        metadata = core.read_pairing(self.actor, issued['pairing_id'])
        self.assertEqual(metadata['runtime_id'], result['runtime_id'])
        self.assertEqual(core.read_runtime(self.actor, result['runtime_id'])['name'], 'Fixed name')
        with self.assertRaises(DomainError): core.consume_pairing(issued['secret'])
        core.revoke(self.actor, result['runtime_id'], 1)
        with self.assertRaises(DomainError): core.authenticate_runtime(result['runtime_token'])

    def test_expiry_and_issuer_current_role(self):
        issued = core.issue_pairing(self.actor, 'Expiry')
        row = RuntimePairing.objects.get(pk=issued['pairing_id'])
        with patch.object(core, '_clock', return_value=row.expires_at):
            with self.assertRaises(DomainError) as error: core.consume_pairing(issued['secret'])
        self.assertEqual(error.exception.code, 'pairing_unavailable')
        self.member.role = 'member'; self.member.save()
        with self.assertRaises(DomainError): core.consume_pairing(issued['secret'])
        self.assertFalse(Runtime.objects.exists())

    def test_human_inputs_and_tenant(self):
        for value in ('', None, 12, 'a'*201):
            with self.assertRaises(DomainError): core.issue_pairing(self.actor, value)
        with self.assertRaises(DomainError): core.issue_pairing(Actor(self.user.pk,self.workspace.pk,'executor'), 'Device')
        issued, result = self.pair()
        for value in (None, True, 1, issued['secret'], 'x'*10000):
            with self.assertRaises(DomainError): core.authenticate_runtime(value)
        other = Workspace.objects.create(name='Other')
        Membership.objects.create(user=self.user, workspace=other, role='admin')
        with self.assertRaises(DomainError): core.read_runtime(Actor(self.user.pk,other.pk),result['runtime_id'])

    def test_secrets_and_read_only_operations(self):
        issued, result = self.pair()
        before = (AuditEvent.objects.count(), Outbox.objects.count())
        core.read_pairing(self.actor, issued['pairing_id']); core.read_runtime(self.actor,result['runtime_id'])
        core.authenticate_runtime(result['runtime_token'])
        self.assertEqual(before, (AuditEvent.objects.count(), Outbox.objects.count()))
        persisted = str(list(AuditEvent.objects.values())) + str(list(Outbox.objects.values())) + str(list(Runtime.objects.values())) + str(list(RuntimePairing.objects.values()))
        for secret in (issued['secret'],result['runtime_token']): self.assertNotIn(secret,persisted)
        self.assertFalse(RegisteredObject.objects.get(kind='runtime',object_id=str(result['runtime_id'])).is_source)

    def test_real_record_failure_rolls_back_and_retry(self):
        original = core.audit.record
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('storage_unavailable','Unavailable',status=503)
        def counts():
            return tuple(model.objects.count() for model in (Runtime,RuntimePairing,RegisteredObject,AuditEvent,Outbox))
        before = counts()
        with patch.object(core.audit,'record',side_effect=fail):
            with self.assertRaises(DomainError): core.issue_pairing(self.actor,'Device')
        self.assertEqual(counts(),before)
        issued = core.issue_pairing(self.actor,'Device'); before = counts()
        with patch.object(core.audit,'record',side_effect=fail):
            with self.assertRaises(DomainError): core.consume_pairing(issued['secret'])
        self.assertEqual(counts(),before)
        core.consume_pairing(issued['secret'])
        self.assertEqual(Runtime.objects.count(),1)

    def test_revoke_cas_repeat_and_authorization(self):
        _, result = self.pair(); pk = result['runtime_id']
        revoked = core.revoke(self.actor,pk,1)
        self.assertEqual(core.revoke(self.actor,pk,2),revoked)
        with self.assertRaises(DomainError): core.revoke(self.actor,pk,1)
        RegisteredObject.objects.filter(kind='runtime',object_id=str(pk)).update(available=False)
        with self.assertRaises(DomainError): core.read_runtime(self.actor,pk)

    def test_two_real_connections_consume_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        issued = core.issue_pairing(self.actor,'Concurrent')
        barrier = Barrier(2)
        def consume():
            connections.close_all()
            barrier.wait()
            try:
                return core.consume_pairing(issued['secret'])
            except DomainError as error:
                return error.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: consume(),range(2)))
        self.assertEqual(sum(isinstance(value,dict) for value in results),1)
        self.assertIn('pairing_unavailable',results)
        self.assertEqual(Runtime.objects.count(),1)
        self.assertEqual(AuditEvent.objects.filter(action_id='runtime.pairing.consume').count(),1)
        self.assertEqual(Outbox.objects.filter(action_id='runtime.pairing.consume').count(),1)
