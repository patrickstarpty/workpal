import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connections
from django.db.models.deletion import ProtectedError
from django.test import TransactionTestCase
from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.access.service import derive_scope
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.delivery import artifacts as service
from workpal.delivery.models import Upload, UploadChunk, Artifact, ArtifactBlob
from workpal.identity.models import Membership
from workpal.storage import MAX_SQLITE_INTEGER


def digest(data):
    return hashlib.sha256(data).hexdigest()


class PublishFixtures(AccessFixtures):
    def upload(self, data=b'abcdef', actor=None, sources=(), key='begin'):
        actor = actor or self.actor
        result = self.act(actor, 'artifact.upload.begin', {'filename': '证据.bin', 'size': len(data),
            'source_refs': [{'kind': source.kind, 'id': source.id} for source in sources]}, key=key)
        for offset in range(0, len(data), service.MAX_CHUNK):
            service.append(actor, result.data['id'], offset, data[offset:offset + service.MAX_CHUNK])
        return result.data

    def finish(self, upload, data=b'abcdef', actor=None, key='finish'):
        return self.act(actor or self.actor, 'artifact.upload.finish',
                        {'upload_id': upload['id'], 'sha256': digest(data)}, key=key)

    def snapshot(self):
        return {model._meta.label: list(model.objects.order_by('pk').values()) for model in apps.get_models()}

    def other_actor(self):
        user = get_user_model().objects.create(username='other-owner')
        Membership.objects.create(user=user, workspace=self.workspace, role='owner')
        return Actor(user.pk, self.workspace.pk)

    def grant_to(self, actor, source, write=False):
        return SourceGrant.objects.create(user_id=actor.user_id,
            source=RegisteredObject.objects.get(kind=source.kind, object_id=source.id), read=True, write=write)


class ArtifactPublishReview(PublishFixtures, WorkpalCase):
    def test_multiblock_publish_clears_staging_and_reads_exact_binary_ranges(self):
        data = b'a' * service.MAX_CHUNK + b'\x00\xff\r\nbinary-tail'
        upload = self.upload(data)
        self.assertEqual(UploadChunk.objects.count(), 2)
        artifact = self.finish(upload, data).data
        self.assertEqual(set(artifact), {'id', 'filename', 'media_type', 'size', 'sha256', 'owner_user_id', 'created_at'})
        self.assertEqual((artifact['size'], artifact['sha256'], artifact['owner_user_id']),
                         (len(data), digest(data), self.user.pk))
        self.assertFalse(UploadChunk.objects.exists())
        current = service.status(self.actor, upload['id'])
        self.assertEqual((current['status'], current['artifact_id'], current['offset']), ('completed', artifact['id'], len(data)))
        self.assertEqual(service.read_chunk(self.actor, artifact['id'], 0), data[:service.MAX_CHUNK])
        self.assertEqual(service.read_chunk(self.actor, artifact['id'], service.MAX_CHUNK - 2, 8),
                         data[service.MAX_CHUNK - 2:service.MAX_CHUNK + 6])
        self.assertEqual(service.read_chunk(self.actor, artifact['id'], service.MAX_CHUNK), data[service.MAX_CHUNK:])
        self.assertEqual(service.read_chunk(self.actor, artifact['id'], len(data)), b'')
        before = Outbox.objects.count()
        self.assertEqual(self.act(self.actor, 'artifact.read', {'artifact_id': artifact['id']}).data, artifact)
        self.assertEqual(Outbox.objects.count(), before)

    def test_empty_file_is_real_verified_artifact_and_closed_upload_rejects_append(self):
        upload = self.upload(b'')
        artifact = self.finish(upload, b'').data
        self.assertEqual(ArtifactBlob.objects.get().content, b'')
        self.assertEqual((artifact['size'], artifact['sha256']), (0, digest(b'')))
        self.assertEqual(service.read_chunk(self.actor, artifact['id'], 0), b'')
        with self.assertRaises(DomainError) as caught:
            service.append(self.actor, upload['id'], 0, b'x')
        self.assertEqual((caught.exception.status, caught.exception.code), (409, 'upload_closed'))

    def test_incomplete_wrong_and_invalid_hashes_preserve_staging_until_correct_finish(self):
        upload = service.begin(self.actor, {'filename': 'Partial', 'size': 6})
        service.append(self.actor, upload['id'], 0, b'abc')
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.finish(upload)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.snapshot(), before)
        service.append(self.actor, upload['id'], 3, b'def')
        before = self.snapshot()
        for value, expected in [('0' * 64, 409), (None, 400), (True, 400), ('A' * 64, 400), ('bad', 400)]:
            with self.subTest(value=value), self.assertRaises(DomainError) as caught:
                self.act(self.actor, 'artifact.upload.finish', {'upload_id': upload['id'], 'sha256': value}, key='finish')
            self.assertEqual(caught.exception.status, expected)
            self.assertEqual(self.snapshot(), before)
        self.assertFalse(Artifact.objects.exists())
        self.assertFalse(ArtifactBlob.objects.exists())
        artifact = self.finish(upload).data
        self.assertEqual(service.read_chunk(self.actor, artifact['id'], 0), b'abcdef')

    def test_finish_replays_keep_identity_and_only_one_publishing_event(self):
        upload = self.upload()
        first = self.finish(upload).data
        self.assertEqual(self.finish(upload).data, first)
        self.assertEqual(service.finish(self.actor, upload['id'], digest(b'abcdef')), first)
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            service.finish(self.actor, upload['id'], digest(b'changed'))
        self.assertEqual(caught.exception.status, 409)
        with self.assertRaises(DomainError) as caught:
            service.append(self.actor, upload['id'], 0, b'abcdef')
        self.assertEqual(caught.exception.code, 'upload_closed')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((Artifact.objects.count(), ArtifactBlob.objects.count()), (1, 1))
        self.assertEqual(AuditEvent.objects.filter(action_id='artifact.upload.finish').count(), 1)
        self.assertEqual(Outbox.objects.filter(action_id='artifact.upload.finish').count(), 1)
        self.assertEqual(IdempotencyResult.objects.filter(action_id='artifact.upload.finish').count(), 1)

    def test_equal_bytes_have_independent_owners_and_sources_when_sharing_physical_blob(self):
        self.grant(self.a, read=True, write=True)
        other = self.other_actor()
        self.grant_to(other, self.b, write=True)
        first = self.finish(self.upload(sources=[self.a])).data
        second = self.finish(self.upload(actor=other, sources=[self.b]), actor=other).data
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual((first['owner_user_id'], second['owner_user_id']), (self.user.pk, other.user_id))
        self.assertEqual((Artifact.objects.count(), ArtifactBlob.objects.count()), (2, 1))
        self.assertEqual(derive_scope([service.artifact_ref(first['id'])]).source_refs, {self.a})
        self.assertEqual(derive_scope([service.artifact_ref(second['id'])]).source_refs, {self.b})
        for actor, row in ((other, first), (self.actor, second)):
            with self.assertRaises(DomainError) as caught:
                service.read_chunk(actor, row['id'], 0)
            self.assertEqual(caught.exception.status, 403)
        self.assertEqual(service.read_chunk(other, second['id'], 0), b'abcdef')
        self.assertFalse({'blob_id', 'deduplicated', 'exists'} & set(second))

    def test_equal_bytes_in_other_workspace_do_not_share_blob_or_read_authority(self):
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        actor = Actor(self.user.pk, self.other.pk)
        first = self.finish(self.upload()).data
        second = self.finish(self.upload(actor=actor), actor=actor).data
        self.assertEqual(ArtifactBlob.objects.count(), 2)
        for who, row in ((actor, first), (self.actor, second)):
            with self.assertRaises(DomainError) as caught:
                service.read(who, row['id'])
            self.assertEqual((caught.exception.status, caught.exception.code), (404, 'not_found'))

    def test_another_owner_cannot_finish_draft_but_can_read_published_content_with_read_grant(self):
        self.grant(self.a, read=True, write=True)
        other = self.other_actor()
        self.grant_to(other, self.a)
        upload = self.upload(sources=[self.a])
        before = self.snapshot()
        for operation in (lambda: service.finish(other, upload['id'], digest(b'abcdef')),
                          lambda: self.finish(upload, actor=other)):
            with self.assertRaises(DomainError) as caught:
                operation()
            self.assertEqual((caught.exception.status, caught.exception.code), (404, 'not_found'))
        self.assertEqual(self.snapshot(), before)
        artifact = self.finish(upload).data
        self.assertEqual(service.read_chunk(other, artifact['id'], 0), b'abcdef')
        with self.assertRaises(DomainError) as caught:
            self.finish(upload, actor=other)
        self.assertEqual(caught.exception.status, 404)

    def test_completed_replays_require_current_upload_write_and_current_artifact_read(self):
        upload_grant = self.grant(self.a, read=True, write=True)
        extra = self.grant(self.b, read=True, write=False)
        upload = self.upload(sources=[self.a])
        artifact = self.finish(upload).data
        self.register(self.workspace.pk, service.artifact_ref(artifact['id']), [self.b])
        extra.read = False
        extra.save()
        for operation in (lambda: service.finish(self.actor, upload['id'], digest(b'abcdef')),
                          lambda: self.finish(upload), lambda: service.read(self.actor, artifact['id'])):
            with self.assertRaises(DomainError) as caught:
                operation()
            self.assertEqual(caught.exception.status, 403)
        extra.read = True
        extra.save()
        upload_grant.write = False
        upload_grant.save()
        self.assertEqual(service.read_chunk(self.actor, artifact['id'], 0), b'abcdef')
        with self.assertRaises(DomainError) as caught:
            self.finish(upload)
        self.assertEqual(caught.exception.status, 403)
        self.member.delete()
        with self.assertRaises(DomainError) as caught:
            service.read_chunk(self.actor, artifact['id'], 0)
        self.assertEqual(caught.exception.status, 404)

    def test_each_chunk_read_rechecks_current_source_permission(self):
        grant = self.grant(self.a, read=True, write=True)
        artifact = self.finish(self.upload(sources=[self.a])).data
        self.assertEqual(service.read_chunk(self.actor, artifact['id'], 0, 3), b'abc')
        grant.read = False
        grant.save()
        with self.assertRaises(DomainError) as caught:
            service.read_chunk(self.actor, artifact['id'], 3, 3)
        self.assertEqual(caught.exception.status, 403)

    def test_late_registration_and_audit_failures_restore_staging_and_retry_same_key(self):
        for module, name in ((service, 'register_object'), (registry, 'record')):
            upload = self.upload(key=name)
            original = getattr(module, name)
            def fail_after_write(*args, **kwargs):
                original(*args, **kwargs)
                raise DomainError('unavailable', 'Try again.', status=503)
            before = self.snapshot()
            with patch.object(module, name, fail_after_write):
                with self.assertRaises(DomainError) as caught:
                    self.finish(upload, key=name)
            self.assertEqual(caught.exception.status, 503)
            self.assertEqual(self.snapshot(), before)
            artifact = self.finish(upload, key=name).data
            self.assertEqual(self.finish(upload, key=name).data, artifact)
            self.assertEqual(service.read_chunk(self.actor, artifact['id'], 0), b'abcdef')
        self.assertEqual((Artifact.objects.count(), ArtifactBlob.objects.count()), (2, 1))

    def test_existing_blob_must_contain_actual_matching_bytes_before_reuse(self):
        self.finish(self.upload())
        blob = ArtifactBlob.objects.get()
        blob.content = b'damaged'
        blob.save(update_fields=['content'])
        upload = self.upload(key='second')
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.finish(upload, key='second')
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.snapshot(), before)
        blob.content = b'abcdef'
        blob.save(update_fields=['content'])
        artifact = self.finish(upload, key='second').data
        self.assertEqual(service.read_chunk(self.actor, artifact['id'], 0), b'abcdef')
        self.assertEqual((Artifact.objects.count(), ArtifactBlob.objects.count()), (2, 1))

    def test_ids_and_binary_range_inputs_are_strict_without_side_effects(self):
        upload = self.upload()
        artifact = self.finish(upload).data
        before = self.snapshot()
        for value in (True, None, '1', 0, -1, MAX_SQLITE_INTEGER + 1):
            for operation in (lambda: service.read(self.actor, value),
                              lambda: service.read_chunk(self.actor, value, 0),
                              lambda: service.finish(self.actor, value, digest(b'abcdef'))):
                with self.subTest(value=value), self.assertRaises(DomainError) as caught:
                    operation()
                self.assertEqual(caught.exception.status, 400)
        for offset, length in ((True, 1), (None, 1), ('0', 1), (-1, 1), (7, 1),
                               (0, True), (0, None), (0, '1'), (0, 0), (0, service.MAX_CHUNK + 1)):
            with self.subTest(offset=offset, length=length), self.assertRaises(DomainError) as caught:
                service.read_chunk(self.actor, artifact['id'], offset, length)
            self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.snapshot(), before)

    def test_publishing_records_all_sources_without_content_in_audit_or_cached_result(self):
        self.grant(self.a, read=True, write=True)
        self.grant(self.b, read=True, write=True)
        data = b'content-not-for-audit-fields'
        upload = self.upload(data, sources=[self.a, self.b])
        result = self.finish(upload, data)
        self.assertEqual(result.object_refs, [service.artifact_ref(result.data['id'])])
        for record in (AuditEvent.objects.get(action_id='artifact.upload.finish'), Outbox.objects.get(action_id='artifact.upload.finish')):
            for ref in (self.a, self.b, service.ref(upload['id']), service.artifact_ref(result.data['id'])):
                self.assertIn({'kind': ref.kind, 'id': ref.id}, record.scope_refs)
        event = AuditEvent.objects.get(action_id='artifact.upload.finish')
        cached = IdempotencyResult.objects.get(action_id='artifact.upload.finish')
        self.assertNotIn(data.decode(), json.dumps([event.fields, cached.result]))

    def test_pending_upload_never_exposes_an_artifact(self):
        upload = self.upload()
        self.assertFalse(Artifact.objects.exists())
        self.assertFalse(ArtifactBlob.objects.exists())
        self.assertEqual(service.status(self.actor, upload['id'])['artifact_id'], 0)
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, 'artifact.read', {'artifact_id': upload['id']})
        self.assertEqual(caught.exception.status, 404)

    def test_published_content_and_owner_are_protected_from_cascading_deletion(self):
        self.finish(self.upload())
        before = self.snapshot()
        for row in (ArtifactBlob.objects.get(), Artifact.objects.get(), self.user):
            with self.assertRaises(ProtectedError):
                row.delete()
        self.assertEqual(self.snapshot(), before)


class ConcurrentPublish(PublishFixtures, TransactionTestCase):
    act = WorkpalCase.act

    def race(self, same_upload):
        first = self.upload()
        second = first if same_upload else self.upload(key='second')
        barrier = Barrier(2)
        def run(item):
            index, upload = item
            connections.close_all()
            try:
                connection = connections['default']
                connection.ensure_connection()
                identity = id(connection.connection)
                barrier.wait(timeout=10)
                result = registry.execute(self.actor, ActionRequest('artifact.upload.finish',
                    {'upload_id': upload['id'], 'sha256': digest(b'abcdef')}, None, 'finish' if same_upload else str(index)))
                return identity, result.data
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, enumerate((first, second))))
        self.assertNotEqual(results[0][0], results[1][0])
        self.assertEqual(ArtifactBlob.objects.count(), 1)
        self.assertFalse(UploadChunk.objects.exists())
        count = 1 if same_upload else 2
        self.assertEqual(Artifact.objects.count(), count)
        self.assertEqual(AuditEvent.objects.filter(action_id='artifact.upload.finish').count(), count)
        self.assertEqual(Outbox.objects.filter(action_id='artifact.upload.finish').count(), count)
        self.assertEqual(IdempotencyResult.objects.filter(action_id='artifact.upload.finish').count(), count)
        return results[0][1], results[1][1]

    def test_same_key_finishes_one_upload_once_across_two_connections(self):
        first, second = self.race(True)
        self.assertEqual(first, second)

    def test_two_uploads_publish_independent_artifacts_while_deduplicating_blob_concurrently(self):
        first, second = self.race(False)
        self.assertNotEqual(first['id'], second['id'])
