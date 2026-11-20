from unittest.mock import patch

from tests.support import WorkpalCase
from tests.test_delivery_selection_review import SelectionFixtures
from workpal.access.models import SourceGrant
from workpal.actions import registry
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError, ObjectRef, SubjectRef
from workpal.delivery import selection
from workpal.delivery.models import DeliveryCurrent, DeliverySelection
from workpal.identity.models import Membership
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work import issues, service as projects


class SelectionHistoryReview(SelectionFixtures, WorkpalCase):
    def history(self, actor=None, subject=None, **page):
        return self.act(actor or self.actor, 'delivery.selections.list',
                        dict(subject=subject or self.subject, **page))

    def test_private_prefix_middle_tail_and_current_do_not_hide_authorized_old_events(self):
        public = self.submit('public')
        private = self.submit('private', artifact_ids=[self.published_artifact()['id']])
        for revision, target in enumerate((private, public, public, private, public, public, private), 1):
            self.choose(target, 'choice-' + str(revision), revision, reason='Reason ' + str(revision))
        events = list(DeliverySelection.objects.order_by('revision'))
        grant = SourceGrant.objects.get(user=self.user, source__kind=self.b.kind, source__object_id=self.b.id)
        grant.read = False
        grant.save()
        outbox_before = Outbox.objects.count()
        with self.assertRaises(DomainError) as caught:
            self.current()
        self.assertEqual(caught.exception.status, 403)
        first = self.history(limit=1)
        self.assertEqual([row['id'] for row in first.data['items']], [events[2].pk])
        self.assertEqual(first.data['next_cursor'], events[2].pk)
        self.assertEqual(first.data['items'][0]['reason'], 'Reason 3')
        self.assertEqual(first.object_refs, [issues.ref(self.issue['id']), ObjectRef('delivery_selection', str(events[2].pk))])
        audit = AuditEvent.objects.filter(action_id='delivery.selections.list').latest('created_at')
        self.assertIn(dict(kind=self.a.kind, id=self.a.id), audit.scope_refs)
        self.assertNotIn(dict(kind=self.b.kind, id=self.b.id), audit.scope_refs)
        self.assertNotIn('Reason', str(audit.fields))
        second = self.history(cursor=first.data['next_cursor'], limit=1).data
        self.assertEqual([row['id'] for row in second['items']], [events[5].pk])
        self.assertEqual(second['next_cursor'], 0)
        self.assertEqual(self.history(cursor=events[5].pk).data, dict(items=[], next_cursor=0))
        self.assertEqual(Outbox.objects.count(), outbox_before)
        self.assertEqual(DeliveryCurrent.objects.get().current_delivery_id, private['id'])
        grant.read = True
        grant.save()
        self.choose(public, 'back-to-public', 8)
        grant.read = False
        grant.save()
        self.assertEqual(self.current().data['current_delivery_id'], public['id'])
        self.assertEqual([row['id'] for row in self.history().data['items']], [events[2].pk, events[5].pk])

    def test_readonly_executor_can_read_archived_history_until_subject_revocation(self):
        self.choose(self.submit('target'), 'chosen', 1)
        expected = self.history().data
        self.act(self.actor, 'issue.archive', dict(issue_id=self.issue['id']), key='archive', revision=1)
        self.member.role = 'member'
        self.member.save()
        SourceGrant.objects.filter(user=self.user).update(write=False, publish=False)
        reader = Actor(self.user.pk, self.workspace.pk, executor_id='history-reader')
        before = Outbox.objects.count()
        self.assertEqual(self.history(reader).data, expected)
        self.assertEqual(expected['items'][0]['actor_user_id'], self.user.pk)
        self.assertEqual(Outbox.objects.count(), before)
        SourceGrant.objects.filter(user=self.user, source__kind=self.a.kind, source__object_id=self.a.id).update(read=False)
        state = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.history(reader)
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), state)

    def test_shared_user_histories_are_isolated_by_workspace_and_subject(self):
        self.choose(self.submit('local'), 'local-choice', 1)
        local = self.history().data
        other_issue = issues.create(self.actor, self.project['id'], 'Other subject')
        other_subject = dict(type='issue', id=str(other_issue['id']))
        target = self.act(self.actor, 'delivery.submit', dict(subject=other_subject,
            requirements_revision=1, summary='Other delivery'), key='other-delivery').data
        self.choose(target, 'other-choice', 1)
        separate = self.history(subject=other_subject).data
        self.assertEqual(len(separate['items']), 1)
        self.assertEqual(separate['items'][0]['subject'], other_subject)
        self.assertNotEqual(separate['items'][0]['id'], local['items'][0]['id'])
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        foreign_actor = Actor(self.user.pk, self.other.pk)
        project = projects.create(foreign_actor, 'Foreign project')
        issue = issues.create(foreign_actor, project['id'], 'Foreign subject')
        foreign_subject = dict(type='issue', id=str(issue['id']))
        target = self.act(foreign_actor, 'delivery.submit', dict(subject=foreign_subject,
            requirements_revision=1, summary='Foreign delivery'), key='foreign-delivery').data
        self.choose(target, 'foreign-choice', 1, actor=foreign_actor)
        foreign = self.history(foreign_actor, foreign_subject).data
        self.assertEqual(len(foreign['items']), 1)
        self.assertEqual(foreign['items'][0]['subject'], foreign_subject)
        self.assertEqual(self.history().data, local)
        before = self.snapshot()
        for actor, subject in ((self.actor, foreign_subject), (foreign_actor, self.subject)):
            with self.subTest(subject=subject), self.assertRaises(DomainError) as caught:
                self.history(actor, subject)
            self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.snapshot(), before)

    def test_late_access_audit_failure_rolls_back_then_plain_read_retries(self):
        self.choose(self.submit('target'), 'chosen', 1)
        before = self.snapshot()
        original = registry.record
        def broken(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('storage_unavailable', 'Retry later.', status=503)
        with patch.object(registry, 'record', broken), self.assertRaises(DomainError) as caught:
            self.history()
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.history().data['items']), 1)
        self.assertEqual(AuditEvent.objects.filter(action_id='delivery.selections.list').count(), 1)
        self.assertFalse(Outbox.objects.filter(action_id='delivery.selections.list').exists())

    def test_empty_boundaries_and_invalid_subjects_do_not_create_selection_state(self):
        before = self.snapshot()
        for subject in ({}, dict(type='issue', id=True), dict(type='issue', id='01'),
                        dict(type='issue', id='1' * 5000), dict(type='automation_run', id='1')):
            with self.subTest(subject=repr(subject)[:80]):
                with self.assertRaises(DomainError) as caught:
                    self.act(self.actor, 'delivery.selections.list', dict(subject=subject))
                self.assertEqual(caught.exception.status, 400)
        with self.assertRaises(DomainError):
            self.act(self.actor, 'delivery.selections.list', dict(subject=self.subject, actor_id=self.user.pk))
        for subject in (None, SubjectRef('issue', None), SubjectRef('issue', '01')):
            with self.subTest(subject=subject), self.assertRaises(DomainError):
                selection.list_history(self.actor, subject)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.history(cursor=MAX_SQLITE_INTEGER - 1, limit=200).data, dict(items=[], next_cursor=0))
        self.assertFalse(DeliveryCurrent.objects.exists())
        self.assertFalse(DeliverySelection.objects.exists())
