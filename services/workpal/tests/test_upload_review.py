from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.access.service import derive_scope
from workpal.actions import registry
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError
from workpal.delivery import artifacts
from workpal.delivery.models import Upload, UploadChunk
from workpal.identity.models import Membership
from workpal.storage import MAX_SQLITE_INTEGER


class UploadReview(AccessFixtures, WorkpalCase):
    def snapshot(self):
        return {model._meta.label: list(model.objects.order_by('pk').values()) for model in apps.get_models()}

    def begin(self, **values):
        return self.act(self.actor, 'artifact.upload.begin', {'filename': 'Notes', 'size': 6, **values}, key='upload')

    def test_service_and_registry_reject_out_of_range_or_noninteger_upload_ids(self):
        self.begin()
        before = self.snapshot()
        for upload_id in (None, True, '1', 0, -1, MAX_SQLITE_INTEGER + 1, 10**100):
            for operation in (lambda: artifacts.status(self.actor, upload_id),
                              lambda: artifacts.append(self.actor, upload_id, 0, b'a'),
                              lambda: self.act(self.actor, 'artifact.upload.read', {'upload_id': upload_id})):
                with self.subTest(upload_id=upload_id), self.assertRaises(DomainError) as caught:
                    operation()
                self.assertEqual((caught.exception.status, caught.exception.code), (400, 'invalid_input'))
        self.assertEqual(self.snapshot(), before)

    def test_closed_metadata_and_falsey_source_values_reject_without_writes(self):
        before = self.snapshot()
        changes = [{'filename': value} for value in (None, False, 'x\0y', 'x\ry', 'x' * 256)]
        changes += [{'media_type': value} for value in (None, False, 'text/plain; charset=utf-8', 'text/plain\r\n')]
        changes += [{'size': value} for value in (-1, artifacts.MAX_SIZE + 1, 1.0, '1')]
        changes += [{'source_refs': value} for value in (None, {}, False, '', [None],
                    [{'kind': 'source', 'id': 'a', 'extra': 1}], [{'kind': 'x' * 101, 'id': 'a'}],
                    [{'kind': 'source', 'id': '\ud800'}])]
        for fields in changes:
            payload = {'filename': 'Notes', 'size': 0, **fields}
            for operation in (lambda: artifacts.begin(self.actor, payload),
                              lambda: self.act(self.actor, 'artifact.upload.begin', payload, key='bad')):
                with self.subTest(fields=fields), self.assertRaises(DomainError) as caught:
                    operation()
                self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.snapshot(), before)

    def test_current_write_permission_is_required_even_for_duplicate_block_and_begin_replay(self):
        grant = self.grant(self.a, read=True, write=True)
        payload = {'filename': 'Notes', 'size': 6, 'source_refs': [{'kind': self.a.kind, 'id': self.a.id}]}
        upload = self.act(self.actor, 'artifact.upload.begin', payload, key='upload').data
        artifacts.append(self.actor, upload['id'], 0, b'abc')
        grant.write = False
        grant.save()
        self.assertEqual(artifacts.status(self.actor, upload['id'])['offset'], 3)
        before = self.snapshot()
        for operation in (lambda: artifacts.append(self.actor, upload['id'], 0, b'abc'),
                          lambda: artifacts.append(self.actor, upload['id'], 3, b'def'),
                          lambda: self.act(self.actor, 'artifact.upload.begin', payload, key='upload')):
            with self.assertRaises(DomainError) as caught:
                operation()
            self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
        grant.read = False
        grant.save()
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, 'artifact.upload.read', {'upload_id': upload['id']})
        self.assertEqual(caught.exception.status, 403)
        self.member.delete()
        with self.assertRaises(DomainError) as caught:
            artifacts.append(self.actor, upload['id'], 0, b'abc')
        self.assertEqual(caught.exception.status, 404)

    def test_other_owner_and_shared_member_in_another_workspace_cannot_read_or_append(self):
        upload = self.begin().data
        artifacts.append(self.actor, upload['id'], 0, b'abc')
        user = get_user_model().objects.create(username='other-owner')
        Membership.objects.create(user=user, workspace=self.workspace, role='owner')
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        before = self.snapshot()
        for actor in (Actor(user.pk, self.workspace.pk), Actor(self.user.pk, self.other.pk)):
            for operation in (lambda: artifacts.status(actor, upload['id']),
                              lambda: artifacts.append(actor, upload['id'], 0, b'abc'),
                              lambda: artifacts.append(actor, upload['id'], 3, b'def'),
                              lambda: self.act(actor, 'artifact.upload.read', {'upload_id': upload['id']})):
                with self.assertRaises(DomainError) as caught:
                    operation()
                self.assertEqual((caught.exception.status, caught.exception.code), (404, 'not_found'))
        self.assertEqual(self.snapshot(), before)

    def test_all_sources_are_required_and_preserved_in_audit_and_outbox(self):
        self.member.role = 'owner'
        self.member.save()
        self.grant(self.a, read=True, write=True)
        refs = [{'kind': ref.kind, 'id': ref.id} for ref in (self.a, self.b)]
        with self.assertRaises(DomainError) as caught:
            self.begin(source_refs=refs)
        self.assertEqual(caught.exception.status, 403)
        self.assertFalse(Upload.objects.exists())
        second = self.grant(self.b, read=True, write=True)
        result = self.begin(source_refs=refs)
        self.assertEqual(derive_scope(result.object_refs).source_refs, {self.a, self.b})
        for entry in (AuditEvent.objects.get(), Outbox.objects.get()):
            for ref in refs:
                self.assertIn(ref, entry.scope_refs)
        self.assertEqual(self.begin(source_refs=refs).data, result.data)
        second.delete()
        with self.assertRaises(DomainError) as caught:
            artifacts.status(self.actor, result.data['id'])
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual((Upload.objects.count(), AuditEvent.objects.count(), Outbox.objects.count()), (1, 1, 1))

    def test_late_registration_and_audit_failures_roll_back_all_tables_and_retry_keys(self):
        for module, name in ((artifacts, 'register_object'), (registry, 'record')):
            original = getattr(module, name)
            def fail_after_write(*args, **kwargs):
                original(*args, **kwargs)
                raise DomainError('unavailable', 'Try again.', status=503)
            payload = {'filename': name, 'size': 0}
            before = self.snapshot()
            with patch.object(module, name, fail_after_write):
                with self.assertRaises(DomainError) as caught:
                    self.act(self.actor, 'artifact.upload.begin', payload, key=name)
            self.assertEqual(caught.exception.status, 503)
            self.assertEqual(self.snapshot(), before)
            result = self.act(self.actor, 'artifact.upload.begin', payload, key=name)
            self.assertEqual(self.act(self.actor, 'artifact.upload.begin', payload, key=name).data, result.data)
        self.assertEqual((Upload.objects.count(), AuditEvent.objects.count(), Outbox.objects.count()), (2, 2, 2))

    def test_append_failure_after_chunk_insert_rolls_back_offset_and_bytes(self):
        upload = self.begin().data
        original = UploadChunk.objects.create
        def fail_after_chunk(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('unavailable', 'Try again.', status=503)
        before = self.snapshot()
        with patch.object(UploadChunk.objects, 'create', fail_after_chunk):
            with self.assertRaises(DomainError) as caught:
                artifacts.append(self.actor, upload['id'], 0, b'abc')
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(artifacts.append(self.actor, upload['id'], 0, b'abc'), 3)
        self.assertEqual(UploadChunk.objects.count(), 1)

    def test_begin_replay_is_original_result_but_status_reports_current_resume_offset(self):
        first = self.begin()
        artifacts.append(self.actor, first.data['id'], 0, b'abc')
        artifacts.append(self.actor, first.data['id'], 3, b'def')
        self.assertEqual(self.begin().data, first.data)
        current = self.act(self.actor, 'artifact.upload.read', {'upload_id': first.data['id']}).data
        self.assertEqual((current['offset'], current['status'], current['artifact_id']), (6, 'open', 0))
        self.assertEqual(Outbox.objects.count(), 1)
