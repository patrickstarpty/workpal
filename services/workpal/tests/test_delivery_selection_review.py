from unittest.mock import patch

from django.apps import apps
from django.db import connection
from django.db.models.deletion import ProtectedError
from django.test.utils import CaptureQueriesContext
from tests.support import WorkpalCase
from tests.test_delivery import DeliveryFixtures
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.access.service import authorize, derive_scope
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError, ObjectRef, SubjectRef
from workpal.delivery import selection, service
from workpal.delivery.models import Delivery, DeliveryCurrent, DeliverySelection
from workpal.identity.models import Membership
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work.models import Issue, IssueRequirements


class SelectionFixtures(DeliveryFixtures):
    def submit(self, key, **extra):
        return self.act(self.actor, 'delivery.submit', dict(subject=self.subject,
            requirements_revision=1, summary=key, **extra), key=key).data

    def choose(self, delivery, key, revision, reason='A deliberate human choice.', actor=None):
        return self.act(actor or self.actor, 'delivery.select_current',
            dict(delivery_id=delivery['id'], reason=reason), key=key, revision=revision)

    def current(self, actor=None):
        return self.act(actor or self.actor, 'delivery.current.read', dict(subject=self.subject))

    def snapshot(self):
        return {m._meta.label: list(m.objects.order_by('pk').values()) for m in apps.get_models()}


class SelectionReview(SelectionFixtures, WorkpalCase):
    def test_current_metadata_read_does_not_load_delivery_snapshots(self):
        target = self.submit('target')
        self.choose(target, 'choose', 1)
        with CaptureQueriesContext(connection) as queries:
            result = self.current()
        self.assertEqual(result.data['current_delivery_id'], target['id'])
        for query in queries:
            for field in ('requirements_snapshot', 'workflow_snapshot', 'artifacts_snapshot', 'evidence'):
                self.assertNotIn('"delivery_delivery"."' + field + '"', query['sql'])

    def test_previous_and_target_write_permissions_and_private_history_are_preserved(self):
        artifact = self.published_artifact()
        private = self.submit('private', artifact_ids=[artifact['id']])
        public = self.submit('public')
        grant = SourceGrant.objects.get(user=self.user, source__kind=self.b.kind, source__object_id=self.b.id)
        grant.write = False
        grant.save()
        with self.assertRaises(DomainError) as caught:
            self.choose(private, 'private', 1)
        self.assertEqual(caught.exception.status, 403)
        grant.write = True
        grant.save()
        old = self.choose(private, 'private', 1, reason='Private source reason.')
        first_event = DeliverySelection.objects.get()
        grant.write = False
        grant.save()
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.choose(public, 'public', 2)
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.current().data, old.data)
        grant.write = True
        grant.save()
        chosen = self.choose(public, 'public', 2)
        last_event = DeliverySelection.objects.order_by('revision').last()
        self.assertEqual(derive_scope([ObjectRef('delivery_selection', str(last_event.pk))]).source_refs,
                         {self.a, self.b})
        grant.read = False
        grant.save()
        result = self.current()
        self.assertEqual(result.data, chosen.data)
        self.assertEqual(set(result.data), {'subject', 'revision', 'current_delivery_id', 'current_delivery_number'})
        event = AuditEvent.objects.filter(action_id='delivery.current.read').latest('created_at')
        self.assertNotIn(dict(kind=self.b.kind, id=self.b.id), event.scope_refs)
        for history in (first_event, last_event):
            with self.assertRaises(DomainError):
                authorize(self.actor, 'read', [ObjectRef('delivery_selection', str(history.pk))])
        for target, key, revision, reason in ((private, 'private', 1, 'Private source reason.'),
                                               (public, 'public', 2, 'A deliberate human choice.')):
            with self.subTest(key=key), self.assertRaises(DomainError):
                self.choose(target, key, revision, reason)

    def test_rework_can_inherit_immutable_selection_without_provenance_cycle(self):
        initial = self.submit('initial')
        self.choose(initial, 'first', 1)
        event = DeliverySelection.objects.get()
        event_ref = ObjectRef('delivery_selection', str(event.pk))
        rework = self.submit('rework', source_refs=[dict(kind=event_ref.kind, id=event_ref.id)])
        result = self.choose(rework, 'next', 2)
        self.assertEqual(result.data['current_delivery_id'], rework['id'])
        self.assertEqual(derive_scope([service.ref(rework['id'])]).source_refs, {self.a})
        self.assertFalse(RegisteredObject.objects.filter(kind__in=('delivery_current', 'current_delivery')).exists())
        self.assertEqual(DeliverySelection.objects.count(), 2)

    def test_archived_issue_keeps_current_and_replay_but_rejects_new_selection(self):
        first, second = self.submit('first'), self.submit('second')
        old = self.choose(first, 'chosen', 1)
        self.act(self.actor, 'issue.archive', dict(issue_id=self.issue['id']), key='archive', revision=1)
        before = self.snapshot()
        self.assertEqual(self.choose(first, 'chosen', 1).data, old.data)
        with self.assertRaises(DomainError) as caught:
            self.choose(second, 'new', 2)
        self.assertEqual((caught.exception.status, caught.exception.code), (409, 'issue_archived'))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.current().data, old.data)

    def test_shared_membership_does_not_allow_foreign_selection_and_revocation_stops_replay(self):
        target = self.submit('target')
        chosen = self.choose(target, 'chosen', 1)
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        other = Actor(self.user.pk, self.other.pk)
        before = self.snapshot()
        for call in (lambda: self.current(other), lambda: self.choose(target, 'other', 1, actor=other)):
            with self.assertRaises(DomainError) as caught:
                call()
            self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.snapshot(), before)
        self.member.delete()
        for call in (lambda: self.current(), lambda: self.choose(target, 'chosen', 1)):
            with self.assertRaises(DomainError): call()
        Membership.objects.create(user=self.user, workspace=self.workspace, role='owner')
        self.assertEqual(self.current().data, chosen.data)

    def test_strict_inputs_and_conflicts_leave_no_partial_selection(self):
        target = self.submit('target')
        before = self.snapshot()
        for value in (True, None, '1', 0, -1, MAX_SQLITE_INTEGER):
            with self.subTest(value=value):
                for call in (lambda: selection.select_current(self.actor, value, 1, 'reason'),
                             lambda: selection.select_current(self.actor, target['id'], value, 'reason')):
                    with self.assertRaises(DomainError) as caught: call()
                    self.assertEqual(caught.exception.status, 400)
        for reason in (None, True, '', ' ', 'x' * 4001, '\ud800'):
            with self.subTest(reason=repr(reason)[:50]), self.assertRaises(DomainError):
                selection.select_current(self.actor, target['id'], 1, reason)
        for subject in (None, SubjectRef('issue', None), SubjectRef('issue', '01')):
            with self.subTest(subject=subject), self.assertRaises(DomainError):
                selection.current(self.actor, subject)
        for field in ('subject', 'actor_id', 'revision', 'source'):
            with self.subTest(field=field), self.assertRaises(DomainError):
                self.act(self.actor, 'delivery.select_current', dict(delivery_id=target['id'], reason='reason',
                         **{field: 1}), key='bad', revision=1)
        self.assertEqual(self.snapshot(), before)
        self.choose(target, 'chosen', 1)
        before = self.snapshot()
        for key, revision, reason in (('chosen', 1, 'Changed reason.'), ('stale', 1, 'reason')):
            with self.subTest(key=key), self.assertRaises(DomainError) as caught:
                self.choose(target, key, revision, reason)
            self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.snapshot(), before)

    def test_first_selection_source_registration_failure_removes_pointer_and_retries(self):
        target = self.submit('first')
        before = self.snapshot()
        original = selection.register_object
        def broken(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('storage_unavailable', 'Retry later.', status=503)
        with patch.object(selection, 'register_object', broken), self.assertRaises(DomainError):
            self.choose(target, 'retry', 1)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(DeliveryCurrent.objects.exists())
        self.assertEqual(self.choose(target, 'retry', 1).data['revision'], 2)

    def test_existing_pointer_rolls_back_after_history_audit_or_idempotency_save(self):
        first, second = self.submit('first'), self.submit('second')
        self.choose(first, 'first', 1)
        issues_before = list(Issue.objects.values())
        requirements_before = list(IssueRequirements.objects.values())
        for target, method in ((DeliverySelection.objects, 'create'), (registry, 'record'),
                               (IdempotencyResult.objects, 'create')):
            original = getattr(target, method)
            def broken(*args, **kwargs):
                original(*args, **kwargs)
                raise DomainError('storage_unavailable', 'Retry later.', status=503)
            revision = DeliveryCurrent.objects.get().revision
            key = 'retry-' + str(revision)
            before = self.snapshot()
            with self.subTest(revision=revision), patch.object(target, method, broken), self.assertRaises(DomainError):
                self.choose(second, key, revision)
            self.assertEqual(self.snapshot(), before)
            saved = self.choose(second, key, revision).data
            self.assertEqual(saved['revision'], revision + 1)
            self.assertEqual(self.choose(second, key, revision).data, saved)
        self.assertEqual(list(Issue.objects.values()), issues_before)
        self.assertEqual(list(IssueRequirements.objects.values()), requirements_before)

    def test_selection_history_protects_previous_delivery_after_pointer_moves(self):
        first, second = self.submit('first'), self.submit('second')
        self.choose(first, 'first', 1)
        self.choose(second, 'second', 2)
        with self.assertRaises(ProtectedError) as caught:
            Delivery.objects.get(pk=first['id']).delete()
        self.assertTrue(any(isinstance(row, DeliverySelection) for row in caught.exception.protected_objects))
        with self.assertRaises(ProtectedError):
            DeliveryCurrent.objects.get().delete()
        self.assertEqual(Delivery.objects.count(), 2)
