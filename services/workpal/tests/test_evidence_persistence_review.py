from django.test import TestCase, SimpleTestCase
from django.contrib.auth import get_user_model
from workpal.identity.models import Membership, Workspace
from workpal.access.models import SourceGrant
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.investigation.normalization import normalize_upload
from tests import test_evidence_policy as fixtures
from workpal.actions.registry import execute
from workpal.actions.schemas import check_schema, validate
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.investigation import evidence
from workpal.investigation.models import Source


class NullableOutputSchemaTests(SimpleTestCase):
    def test_nullable_string_accepts_only_strings_or_null(self):
        schema = {'type': ['string', 'null'], 'maxLength': 64}
        check_schema(schema)
        validate(None, schema)
        validate('2026-11-20T12:00:00+08:00', schema)
        for value in (False, 1, {}, [], 'a' * 65):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(value, schema)

    def test_invalid_unions_remain_rejected(self):
        for kind in ([], ['string'], ['null', 'null'], ['string', 'integer'],
                     ['string', 'null', 'integer'], ['object', 'null'], [True, 'null']):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                check_schema({'type': kind})
        for invalid in ({'type': ['string', 'null'], 'arbitrary': True},
                        {'type': ['string', 'null'], 'minItems': 1}):
            with self.subTest(schema=invalid), self.assertRaises(ValueError):
                check_schema(invalid)


class EvidencePersistenceReviewTests(TestCase):
    setUp = fixtures.EvidencePolicyTests.setUp
    snapshot = fixtures.EvidencePolicyTests.snapshot

    def ready(self):
        evidence.configure_policy(self.actor, self.source, self.policy, 1)
        source = Source.objects.get(pk=self.source)
        data = execute(self.actor, ActionRequest('investigation.start', dict(
            project_id=source.environment.project_id, environment_id=source.environment_id,
            service_id=source.allowed_services.get().pk, problem='Review evidence', key='review'),
            None, 'review')).data
        return data['id']

    def test_member_upload_read_and_current_write_read_revocation(self):
        investigation_id = self.ready()
        user = get_user_model().objects.create(username='evidence-reader')
        Membership.objects.create(user=user, workspace_id=self.actor.workspace_id, role='member')
        member = Actor(user.pk, self.actor.workspace_id)
        for grant in SourceGrant.objects.filter(user_id=self.actor.user_id):
            SourceGrant.objects.create(user=user, source=grant.source, read=True,
                write=grant.source.kind == 'environment', publish=False)
        def upload(key='member-upload'):
            return evidence.submit_upload(member, investigation_id, self.source,
                b'SECRET-literal member', format='text', key=key)
        result = upload()
        self.assertEqual(evidence.read_evidence(member, result['id'])['content'], '[REDACTED] member')
        with self.assertRaises(DomainError):
            evidence.read_policy(member, self.source)
        SourceGrant.objects.filter(user=user, source__kind='environment').update(write=False)
        before = self.snapshot()
        for key in ('member-upload', 'new-denied'):
            with self.assertRaises(DomainError) as caught:
                upload(key)
            self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(evidence.read_evidence(member, result['id'])['content'], '[REDACTED] member')
        SourceGrant.objects.filter(user=user).update(read=False, write=False)
        before = self.snapshot()
        for operation in (upload, lambda: evidence.read_evidence(member, result['id'])):
            with self.assertRaises(DomainError) as caught:
                operation()
            self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)

    def test_hashes_truncation_and_saved_content_scope(self):
        investigation_id = self.ready()
        content = b'\n'.join([b'SECRET-literal record'] * 1001)
        expected = normalize_upload(content, format='text', policy=self.policy)
        result = evidence.submit_upload(self.actor, investigation_id, self.source,
            content, format='text', key='truncation')
        self.assertEqual(result['included_records'], 1000)
        self.assertTrue(result['truncated'])
        for field, value in expected.items():
            if field != 'content':
                self.assertEqual(result[field], value)
        cache = IdempotencyResult.objects.get(action_id='evidence.upload', key='truncation')
        self.assertEqual(cache.result['data'], result)
        self.assertNotIn('content', cache.result['data'])
        self.assertNotIn('SECRET-literal', str(cache.result))
        event = AuditEvent.objects.get(action_id='evidence.upload')
        self.assertEqual(event.fields, dict(investigation_id=investigation_id, source_id=self.source, format='text'))
        self.assertEqual(Outbox.objects.get(event=event).scope_refs, event.scope_refs)
        kinds = {ref['kind'] for ref in event.scope_refs}
        self.assertTrue({'evidence', 'investigation', 'environment', 'environment_service', 'evidence_source'} <= kinds)

    def test_cross_workspace_reads_and_uploads_are_hidden(self):
        investigation_id = self.ready()
        result = evidence.submit_upload(self.actor, investigation_id, self.source,
            b'allowed', format='text', key='cross')
        workspace = Workspace.objects.create(name='Unrelated')
        Membership.objects.create(user_id=self.actor.user_id, workspace=workspace, role='owner')
        other = Actor(self.actor.user_id, workspace.pk)
        before = self.snapshot()
        for operation in (
            lambda: evidence.read_evidence(other, result['id']),
            lambda: evidence.submit_upload(other, investigation_id, self.source, b'allowed', format='text', key='cross')):
            with self.assertRaises(DomainError) as caught:
                operation()
            self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.snapshot(), before)

    def test_real_upload_audit_failure_restores_all_rows(self):
        from unittest.mock import patch
        from workpal.actions import registry
        from workpal.investigation.models import EvidenceSnapshot
        investigation_id = self.ready()
        def upload():
            return evidence.submit_upload(self.actor, investigation_id, self.source,
                b'SECRET-literal rollback', format='text', key='full-rollback')
        original = registry.record
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('storage_unavailable', 'Unavailable.', status=503)
        before = self.snapshot()
        with patch.object(registry, 'record', side_effect=fail):
            with self.assertRaises(DomainError) as caught:
                upload()
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        result = upload()
        self.assertEqual(upload(), result)
        self.assertEqual(EvidenceSnapshot.objects.filter(key='full-rollback').count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action_id='evidence.upload').count(), 1)
        self.assertEqual(Outbox.objects.filter(action_id='evidence.upload').count(), 1)
        self.assertEqual(IdempotencyResult.objects.filter(action_id='evidence.upload').count(), 1)

    def test_explicit_offset_range_roundtrip_and_replay(self):
        evidence.configure_policy(self.actor, self.source, self.policy, 1)
        source = Source.objects.get(pk=self.source)
        investigation = execute(self.actor, ActionRequest('investigation.start', dict(
            project_id=source.environment.project_id, environment_id=source.environment_id,
            service_id=source.allowed_services.get().pk, problem='Range evidence', key='range'),
            None, 'range')).data
        start, end = '2026-11-20T10:00:00+08:00', '2026-11-20T10:30:00+08:00'
        def upload():
            return evidence.submit_upload(self.actor, investigation['id'], self.source,
                b'SECRET-literal range', format='text', timezone='Asia/Shanghai',
                range_start=start, range_end=end, key='explicit-range')
        result = upload()
        self.assertEqual(result['range_start'], start)
        self.assertEqual(result['range_end'], end)
        self.assertEqual(result['timezone'], 'Asia/Shanghai')
        self.assertIsNone(result['event_time'])
        self.assertEqual(upload(), result)
        read = evidence.read_evidence(self.actor, result['id'])
        self.assertEqual(read['content'], '[REDACTED] range')
        self.assertEqual({k: v for k, v in read.items() if k != 'content'}, result)
