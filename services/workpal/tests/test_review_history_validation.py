from unittest.mock import patch

from tests.support import WorkpalCase
from tests.test_review_validation import ReviewFixtures
from workpal.access.models import SourceGrant
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError, ObjectRef, SubjectRef
from workpal.delivery import review
from workpal.delivery.models import DeliveryCurrent, Review
from workpal.identity.models import Membership
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work import issues, service as projects


class ReviewHistoryValidation(ReviewFixtures, WorkpalCase):
    def listing(self, actor=None, subject=None, **page):
        return self.act(actor or self.actor, 'review.list', dict(subject=subject or self.subject, **page))

    def test_delivery_and_requirements_versions_remain_historical_after_switches(self):
        first = self.ready()
        old = self.decide(first, reason='Original requirements accepted.').data
        old_summary = self.listing().data['items'][0]
        updated = self.act(self.actor, 'issue.update', dict(issue_id=self.issue['id'], title='Updated requirements'),
                           key='requirements', revision=1).data
        artifact = self.published_artifact()
        second = self.act(self.actor, 'delivery.submit', dict(subject=self.subject,
            requirements_revision=updated['requirements_revision'], summary='New submission',
            artifact_ids=[artifact['id']], evidence=[dict(criterion_key='documented', artifact_ids=[artifact['id']])]),
            key='new-submission').data
        self.choose(second, 'new-choice', 3)
        newer = self.decide(second, key='new-review', revision=4, reason='New requirements accepted.').data
        self.choose(first, 'old-choice', 5)
        returned = self.decide(first, key='return-old', revision=6, outcome='request_changes',
                               reason='Update to the new requirements.').data
        rows = self.listing().data['items']
        self.assertEqual(rows[0], old_summary)
        self.assertEqual([row['id'] for row in rows], [old['id'], newer['id'], returned['id']])
        self.assertEqual([row['delivery_id'] for row in rows], [first['id'], second['id'], first['id']])
        self.assertEqual([row['version'] for row in rows], [1, 2, 1])
        self.assertEqual([row['requirements_revision'] for row in rows], [1, 2, 1])
        self.assertEqual([row['revision'] for row in rows], [3, 5, 7])
        self.assertFalse({'is_current', 'effective', 'approved', 'requirements_snapshot', 'workflow_snapshot'} & set(rows[0]))

    def test_private_current_and_latest_decision_do_not_hide_public_history_or_leak_private_reason(self):
        target = self.ready()
        old = self.decide(target).data
        private = self.register(self.workspace.pk, ObjectRef('source', 'private-latest-review'), is_source=True)
        grant = self.grant(private, read=True, write=True)
        refs = [dict(kind=private.kind, id=private.id)]
        hidden = self.decide(target, key='private-review', revision=3, outcome='request_changes',
                            reason='Private decision reason.', source_refs=refs).data
        candidate = self.submit('private-candidate', source_refs=refs)
        self.choose(candidate, 'private-current', 4)
        grant.read = False
        grant.save()
        with self.assertRaises(DomainError): self.current()
        outbox_before = Outbox.objects.count()
        result = self.listing(limit=1)
        self.assertEqual([row['id'] for row in result.data['items']], [old['id']])
        self.assertEqual(result.data['next_cursor'], 0)
        self.assertEqual(result.object_refs, [issues.ref(self.issue['id']), review.ref(old['id'])])
        event = AuditEvent.objects.filter(action_id='review.list').latest('created_at')
        scope = {ObjectRef(**value) for value in event.scope_refs}
        self.assertTrue({self.a, self.b, review.ref(old['id']), issues.ref(self.issue['id'])} <= scope)
        self.assertNotIn(private, scope)
        self.assertNotIn(review.ref(hidden['id']), scope)
        self.assertNotIn('Private decision reason.', str(event.fields))
        self.assertEqual(Outbox.objects.count(), outbox_before)
        grant.read = True
        grant.save()
        self.choose(target, 'public-current', 5)
        grant.read = False
        grant.save()
        self.assertEqual(self.current().data['current_delivery_id'], target['id'])
        self.assertEqual(self.listing().data, result.data)

    def test_archived_readonly_executor_history_obeys_artifact_and_subject_revocation(self):
        saved = self.decide(self.ready()).data
        expected = self.listing().data
        self.act(self.actor, 'issue.archive', dict(issue_id=self.issue['id']), key='archive', revision=1)
        self.member.role = 'member'
        self.member.save()
        SourceGrant.objects.filter(user=self.user).update(write=False, publish=False)
        reader = Actor(self.user.pk, self.workspace.pk, executor_id='history-reader')
        self.assertEqual(self.listing(reader).data, expected)
        SourceGrant.objects.filter(user=self.user, source__kind=self.b.kind, source__object_id=self.b.id).update(read=False)
        self.assertEqual(self.listing(reader).data, dict(items=[], next_cursor=0))
        self.assertTrue(Review.objects.filter(pk=saved['id']).exists())
        SourceGrant.objects.filter(user=self.user, source__kind=self.a.kind, source__object_id=self.a.id).update(read=False)
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.listing(reader)
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)

    def test_shared_member_cannot_mix_subjects_or_workspaces(self):
        self.decide(self.ready())
        local = self.listing().data
        task = issues.create(self.actor, self.project['id'], 'Another task')
        other_subject = dict(type='issue', id=str(task['id']))
        target = self.act(self.actor, 'delivery.submit', dict(subject=other_subject,
            requirements_revision=1, summary='Other result'), key='other-result').data
        self.choose(target, 'other-choice', 1)
        other_review = self.decide(target, key='other-review', outcome='request_changes').data
        self.assertEqual([row['id'] for row in self.listing(subject=other_subject).data['items']], [other_review['id']])
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        foreign = Actor(self.user.pk, self.other.pk)
        project = projects.create(foreign, 'Foreign project')
        task = issues.create(foreign, project['id'], 'Foreign task')
        foreign_subject = dict(type='issue', id=str(task['id']))
        target = self.act(foreign, 'delivery.submit', dict(subject=foreign_subject,
            requirements_revision=1, summary='Foreign result'), key='foreign-result').data
        self.choose(target, 'foreign-choice', 1, actor=foreign)
        saved = self.decide(target, key='foreign-review', actor=foreign, outcome='request_changes').data
        self.assertEqual([row['id'] for row in self.listing(foreign, foreign_subject).data['items']], [saved['id']])
        self.assertEqual(self.listing().data, local)
        before = self.snapshot()
        for actor, subject in ((self.actor, foreign_subject), (foreign, self.subject)):
            with self.subTest(subject=subject), self.assertRaises(DomainError) as caught:
                self.listing(actor, subject)
            self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.snapshot(), before)

    def test_authorization_503_during_lookahead_does_not_return_a_partial_page(self):
        target = self.ready()
        first = self.decide(target).data
        second = self.decide(target, key='second', revision=3, outcome='request_changes').data
        original = review.authorize
        def unavailable(actor, capability, refs):
            original(actor, capability, refs)
            if review.ref(second['id']) in refs:
                raise DomainError('storage_unavailable', 'Try later.', status=503)
        before = self.snapshot()
        with patch.object(review, 'authorize', unavailable), self.assertRaises(DomainError) as caught:
            self.listing(limit=1)
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        result = self.listing(limit=1).data
        self.assertEqual([row['id'] for row in result['items']], [first['id']])
        self.assertEqual(result['next_cursor'], first['id'])

    def test_strict_subjects_and_empty_page_do_not_create_business_records(self):
        before = self.snapshot()
        for subject in ({}, dict(type='issue', id=True), dict(type='issue', id='01'),
                        dict(type='issue', id='1' * 5000), dict(type='automation_run', id='1')):
            with self.subTest(subject=repr(subject)[:80]), self.assertRaises(DomainError) as caught:
                self.act(self.actor, 'review.list', dict(subject=subject))
            self.assertEqual(caught.exception.status, 400)
        with self.assertRaises(DomainError):
            self.act(self.actor, 'review.list', dict(subject=self.subject, actor_id=self.user.pk))
        for subject in (None, SubjectRef('issue', None), SubjectRef('issue', '01')):
            with self.subTest(subject=subject), self.assertRaises(DomainError):
                review.list_reviews(self.actor, subject)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.listing(cursor=MAX_SQLITE_INTEGER - 1, limit=200).data, dict(items=[], next_cursor=0))
        self.assertFalse(DeliveryCurrent.objects.exists())
        self.assertFalse(Review.objects.exists())
