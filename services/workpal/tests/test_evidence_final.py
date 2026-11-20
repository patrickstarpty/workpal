"""Final acceptance checks; fixture methods only, no inherited test methods."""
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from tests import test_evidence_persistence_review as fixtures
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.actions import registry
from workpal.investigation import evidence
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.identity.models import Membership

class EvidenceFinalTests(TestCase):
    setUp = fixtures.EvidencePersistenceReviewTests.setUp
    ready = fixtures.EvidencePersistenceReviewTests.ready
    snapshot = fixtures.EvidencePersistenceReviewTests.snapshot

    def prepare(self):
        self.investigation = self.ready()
        self.row = self.upload('initial')
        user = get_user_model().objects.create(username='final-member')
        Membership.objects.create(user=user, workspace_id=self.actor.workspace_id, role='member')
        self.member = Actor(user.pk, self.actor.workspace_id)
        for grant in SourceGrant.objects.filter(user_id=self.actor.user_id):
            SourceGrant.objects.create(user=user, source=grant.source, read=True,
                write=grant.source.kind == 'environment')

    def upload(self, key, actor=None):
        return evidence.submit_upload(actor or self.actor, self.investigation, self.source,
            b'SECRET-literal final', format='text', key=key)

    def test_real_private_evidence_pagination(self):
        self.prepare()
        rows = [self.row] + [self.upload(str(i)) for i in range(20)]
        hidden = {rows[i]['id'] for i in (0, 10, 20)}
        for ident in hidden:
            RegisteredObject.objects.filter(kind='evidence', object_id=str(ident)).update(available=False)
        visible, cursor = [], 0
        while True:
            page = evidence.list_evidence(self.member, self.investigation, cursor, 4)
            visible.extend(page['items'])
            cursor = page['next_cursor']
            if not cursor:
                break
        self.assertEqual(visible, [r for r in rows if r['id'] not in hidden])
        self.assertEqual(len({r['id'] for r in visible}), 18)
        self.assertNotIn('SECRET-literal', str(visible))
        self.assertTrue(all('content' not in r and 'policy' not in r for r in visible))

    def test_current_read_grants(self):
        self.prepare()
        for kind in ('environment', 'environment_service', 'evidence_source', 'investigation', 'evidence'):
            objects = RegisteredObject.objects.filter(kind=kind)
            self.assertTrue(objects.exists())
            objects.update(available=False)
            with self.assertRaises(DomainError):
                evidence.read_evidence(self.member, self.row['id'])
            objects.update(available=True)
            self.assertEqual(evidence.read_evidence(self.member, self.row['id'])['id'], self.row['id'])

    def test_write_revocation_and_capability_cleanup(self):
        self.prepare()
        row = self.upload('member', self.member)
        grant = SourceGrant.objects.filter(user_id=self.member.user_id, source__kind='environment')
        grant.update(write=False)
        for key in ('member', 'new'):
            with self.assertRaises(DomainError) as caught:
                self.upload(key, self.member)
            self.assertEqual(caught.exception.status, 403)
            self.assertIsNone(evidence._prepared.get())
        self.assertEqual(evidence.read_evidence(self.member, row['id'])['id'], row['id'])
        grant.update(write=True)
        self.assertEqual(self.upload('member', self.member), row)

    def test_real_record_503_rolls_back_read_list_upload(self):
        self.prepare()
        original = registry.record
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('unavailable', 'Unavailable.', status=503)
        for operation in (lambda: evidence.read_evidence(self.member, self.row['id']),
                          lambda: evidence.list_evidence(self.member, self.investigation),
                          lambda: self.upload('rollback', self.member)):
            before = self.snapshot()
            with patch.object(registry, 'record', side_effect=fail):
                with self.assertRaises(DomainError) as caught:
                    operation()
            self.assertEqual(caught.exception.status, 503)
            self.assertEqual(self.snapshot(), before)
            self.assertIsNone(evidence._prepared.get())
        row = self.upload('rollback', self.member)
        self.assertEqual(self.upload('rollback', self.member), row)

    def test_direct_registry_default_and_empty(self):
        self.prepare()
        direct = evidence.list_evidence(self.member, self.investigation)
        registered = registry.execute(self.member, ActionRequest('evidence.list',
            dict(investigation_id=self.investigation), None, None)).data
        self.assertEqual(direct, registered)
        self.assertEqual(evidence.list_evidence(self.member, self.investigation,
            cursor=self.row['id']), dict(items=[], next_cursor=0))

    def test_allowed_service_narrowing_blocks_replay(self):
        from workpal.investigation.models import Source
        self.prepare()
        row = self.upload('member', self.member)
        source = Source.objects.get(pk=self.source)
        services = list(source.allowed_services.all())
        source.allowed_services.clear()
        with self.assertRaises(DomainError) as caught:
            self.upload('member', self.member)
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(evidence.list_evidence(self.member, self.investigation)['items'], [])
        source.allowed_services.set(services)
        self.assertEqual(self.upload('member', self.member), row)

from django.test import TransactionTestCase

class EvidenceFinalConcurrencyTests(TransactionTestCase):
    setUp = fixtures.EvidencePersistenceReviewTests.setUp
    ready = fixtures.EvidencePersistenceReviewTests.ready

    def race(self, different):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from django.db import connections
        from workpal.investigation.models import EvidenceSnapshot
        from workpal.actions.models import IdempotencyResult
        from workpal.audit.models import AuditEvent, Outbox
        investigation = self.ready()
        barrier = threading.Barrier(2)
        handles = []
        def worker(index):
            connection = connections['default']
            try:
                connection.ensure_connection()
                handles.append(connection.connection)
                self.assertNotIn('mode=memory', str(connection.settings_dict['NAME']))
                actor = Actor(self.actor.user_id, self.actor.workspace_id)
                barrier.wait(timeout=10)
                for attempt in range(4):
                    try:
                        return evidence.submit_upload(actor, investigation, self.source,
                            str(index if different else 0).encode(), format='text', key='race')
                    except DomainError as error:
                        if error.status == 503 and error.code == 'storage_busy' and attempt < 3:
                            continue
                        return error.status
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, (0, 1)))
        self.assertEqual(len(handles), 2)
        self.assertIsNot(handles[0], handles[1])
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1 if different else 2)
        if different:
            self.assertIn(409, results)
        else:
            self.assertEqual(results[0], results[1])
        self.assertEqual(EvidenceSnapshot.objects.count(), 1)
        for model in (IdempotencyResult, AuditEvent, Outbox):
            self.assertEqual(model.objects.filter(action_id='evidence.upload').count(), 1)

    def test_same_content_two_connections(self):
        self.race(False)

    def test_different_content_two_connections(self):
        self.race(True)
