from copy import deepcopy
from unittest.mock import patch

from django.apps import apps
from django.db.models.deletion import ProtectedError
from tests.support import WorkpalCase
from tests.test_delivery import DeliveryFixtures
from workpal.access.models import SourceGrant
from workpal.access.service import derive_scope
from workpal.actions import registry
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError, ObjectRef, SubjectRef
from workpal.delivery import artifacts, service
from workpal.delivery.models import Artifact, Delivery, DeliveryArtifact, Upload
from workpal.identity.models import Membership
from workpal.storage import MAX_SQLITE_INTEGER


class DeliveryReview(DeliveryFixtures, WorkpalCase):
    def payload(self, **extra):
        return dict(subject=deepcopy(self.subject), requirements_revision=1,
                    summary='Private result description.', **extra)

    def snapshot(self):
        return {m._meta.label: list(m.objects.order_by('pk').values()) for m in apps.get_models()}

    def test_direct_interface_rejects_malformed_subjects_and_submission_shapes(self):
        submission = {'requirements_revision': 1, 'summary': 'A result'}
        before = self.snapshot()
        for bad in (None, {}, SubjectRef('issue', None), SubjectRef('issue', 1),
                    SubjectRef('issue', True), SubjectRef('issue', ''), SubjectRef('issue', '01'),
                    SubjectRef('issue', '0'), SubjectRef('issue', '-1'), SubjectRef('issue', '١'),
                    SubjectRef('issue', str(MAX_SQLITE_INTEGER)), SubjectRef('issue', '1' * 5000),
                    SubjectRef('automation_run', str(self.issue['id']))):
            with self.subTest(subject=repr(bad)[:70]):
                with self.assertRaises(DomainError) as caught:
                    service.submit(self.actor, bad, submission)
                self.assertEqual(caught.exception.status, 400)
        subject = SubjectRef(**self.subject)
        for bad in (None, True, [], ['summary'], 'summary', {}):
            with self.subTest(submission=bad):
                with self.assertRaises(DomainError) as caught:
                    service.submit(self.actor, subject, bad)
                self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.snapshot(), before)

    def test_direct_source_reference_bounds_and_unicode_are_domain_errors(self):
        subject = SubjectRef(**self.subject)
        before = self.snapshot()
        for sources in (None, {}, [{'kind': 'x' * 101, 'id': 'a'}],
                        [{'kind': 'source', 'id': 'a' * 256}],
                        [{'kind': 'source', 'id': '\ud800'}]):
            with self.subTest(sources=repr(sources)):
                with self.assertRaises(DomainError) as caught:
                    service.submit(self.actor, subject, {'requirements_revision': 1, 'summary': 'Result',
                                                         'source_refs': sources})
                self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.snapshot(), before)

    def test_direct_result_snapshots_do_not_alias_input_collections(self):
        artifact = self.published_artifact()
        submission = dict(requirements_revision=1, summary='Human evidence', artifact_ids=[artifact['id']],
                          evidence=[dict(criterion_key='documented', artifact_ids=[artifact['id']])])
        result = service.submit(self.actor, SubjectRef(**self.subject), submission)
        expected = service.read(self.actor, result['id'])
        submission['artifact_ids'].clear()
        submission['evidence'][0]['artifact_ids'].clear()
        self.assertEqual(result, expected)
        result['requirements_snapshot']['criteria'].clear()
        result['workflow_snapshot']['definition']['states'].clear()
        result['artifacts_snapshot'].clear()
        self.assertEqual(service.read(self.actor, result['id']), expected)

    def test_archived_issue_preserves_read_and_replay_but_rejects_new_submission(self):
        payload = self.payload()
        delivery = self.act(self.actor, 'delivery.submit', payload, key='saved').data
        self.act(self.actor, 'issue.archive', {'issue_id': self.issue['id']}, key='archive', revision=1)
        before = self.snapshot()
        self.assertEqual(self.act(self.actor, 'delivery.submit', payload, key='saved').data, delivery)
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, 'delivery.submit', payload, key='new')
        self.assertEqual((caught.exception.status, caught.exception.code), (409, 'issue_archived'))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.act(self.actor, 'delivery.read', {'delivery_id': delivery['id']}).data, delivery)

    def test_delivery_attachment_itself_prevents_artifact_deletion(self):
        artifact = self.published_artifact()
        delivery = self.act(self.actor, 'delivery.submit', self.payload(artifact_ids=[artifact['id']]), key='d').data
        link = DeliveryArtifact.objects.get(delivery_id=delivery['id'], artifact_id=artifact['id'])
        # Remove the separate upload protection to prove this Delivery retains it.
        Upload.objects.filter(artifact_id=artifact['id']).delete()
        with self.assertRaises(ProtectedError) as caught:
            Artifact.objects.get(pk=artifact['id']).delete()
        self.assertIn(link, caught.exception.protected_objects)
        self.assertEqual(artifacts.read(self.actor, artifact['id']), artifact)

    def test_full_provenance_is_inherited_without_restricting_original_artifact(self):
        artifact = self.published_artifact()
        explicit = self.register(self.workspace.pk, ObjectRef('source', 'c'), is_source=True)
        self.grant(explicit, read=True, write=True)
        payload = self.payload(artifact_ids=[artifact['id']], source_refs=[dict(kind=explicit.kind, id=explicit.id)])
        delivery = self.act(self.actor, 'delivery.submit', payload, key='sources').data
        scope = {self.a, self.b, explicit}
        self.assertEqual(derive_scope([service.ref(delivery['id'])]).source_refs, scope)
        self.assertEqual(derive_scope([artifacts.artifact_ref(artifact['id'])]).source_refs, {self.b})
        event = AuditEvent.objects.get(action_id='delivery.submit')
        self.assertTrue(scope <= {ObjectRef(**ref) for ref in event.scope_refs})
        self.assertNotIn(payload['summary'], str(event.fields))
        self.assertEqual(Outbox.objects.get(event=event).scope_refs, event.scope_refs)
        grant = SourceGrant.objects.get(user=self.user, source__kind=self.a.kind, source__object_id=self.a.id)
        grant.write = False
        grant.save()
        self.assertEqual(service.read(self.actor, delivery['id']), delivery)
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, 'delivery.submit', payload, key='sources')
        self.assertEqual(caught.exception.status, 403)
        grant.read = False
        grant.save()
        with self.assertRaises(DomainError):
            service.read(self.actor, delivery['id'])
        self.assertEqual(artifacts.read(self.actor, artifact['id']), artifact)

    def test_same_user_in_two_workspaces_cannot_read_or_submit_foreign_subject(self):
        delivery = self.act(self.actor, 'delivery.submit', self.payload(), key='local').data
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        other = Actor(self.user.pk, self.other.pk)
        before = self.snapshot()
        for action, payload, key in (
            ('delivery.read', {'delivery_id': delivery['id']}, None),
            ('delivery.submit', self.payload(), 'foreign'),
        ):
            with self.subTest(action=action), self.assertRaises(DomainError) as caught:
                self.act(other, action, payload, key=key)
            self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(service.read(self.actor, delivery['id']), delivery)

    def test_late_registration_attachment_and_audit_failures_rollback_then_retry(self):
        artifact = self.published_artifact()
        payload = self.payload(artifact_ids=[artifact['id']])
        for target, name in ((service, 'register_object'), (DeliveryArtifact.objects, 'create'),
                             (registry, 'record')):
            original = getattr(target, name)
            def broken(*args, **kwargs):
                original(*args, **kwargs)
                raise DomainError('temporarily_unavailable', 'Try again.', status=503)
            before = self.snapshot()
            key = 'failed-' + name
            with self.subTest(stage=name), patch.object(target, name, broken), self.assertRaises(DomainError) as caught:
                self.act(self.actor, 'delivery.submit', payload, key=key)
            self.assertEqual(caught.exception.status, 503)
            self.assertEqual(self.snapshot(), before)
            number = Delivery.objects.count() + 1
            saved = self.act(self.actor, 'delivery.submit', payload, key=key).data
            self.assertEqual(saved['number'], number)
            self.assertEqual(self.act(self.actor, 'delivery.submit', payload, key=key).data, saved)
