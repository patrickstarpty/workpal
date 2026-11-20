from workpal.work import issues
from tests.support import WorkpalCase
from tests.test_review_validation import ReviewFixtures
from workpal.work.models import IssueTransition


class CompletionTests(ReviewFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        definition = dict(states=[dict(key='start', label='Start', category='backlog'),
                                  dict(key='finished', label='Finished', category='done')],
                          transitions=[{'from': 'start', 'to': 'finished'}],
                          review_policy=dict(completion='approved_delivery', reviewer_roles=['owner']))
        draft = self.act(self.actor, 'workflow.create', dict(name='Approval', definition=definition), key='workflow').data
        version = self.act(self.actor, 'workflow.publish', dict(draft_id=draft['id']), key='publish', revision=1).data
        confirmation = self.act(self.actor, 'project.set_workflow', dict(project_id=self.project['id'], workflow_version_id=version['id']), key='binding', revision=1)
        self.act(self.actor, 'project.set_workflow', dict(project_id=self.project['id'], workflow_version_id=version['id']), key='binding', revision=1, confirmation_id=confirmation.data['confirmation_id'])
        self.issue = self.act(self.actor, 'issue.create', dict(project_id=self.project['id'], title='Approved work', criteria=[dict(key='documented', text='Document result')]), key='completion-issue').data
        self.subject = dict(type='issue', id=str(self.issue['id']))

    def test_approved_completion(self):
        self.decide(self.ready())
        approval = self.act(self.actor, 'delivery.approval.read', dict(subject=self.subject)).data
        result = self.act(self.actor, 'issue.transition', dict(issue_id=self.issue['id'], target='finished', reason='Accepted'), key='complete', revision=1)
        self.assertEqual(result.data['status_category'], 'done')
        history = IssueTransition.objects.get(issue_id=self.issue['id'])
        self.assertEqual(history.completion_review_id, approval['review_id'])
        self.assertEqual(history.completion_snapshot, approval)

    def complete(self, key='complete', revision=1):
        return self.act(self.actor, 'issue.transition', dict(issue_id=self.issue['id'], target='finished', reason='Accepted'), key=key, revision=revision)

    def test_missing_approval(self):
        from workpal.contracts import DomainError
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.complete()
        self.assertEqual(caught.exception.code, 'completion_not_ready')
        self.assertEqual(before, self.snapshot())

    def test_returned_reselected_and_changed_requirements(self):
        from workpal.contracts import DomainError
        target = self.ready()
        self.decide(target, outcome='request_changes')
        with self.assertRaises(DomainError): self.complete()
        self.decide(target, key='approve', revision=3)
        self.choose(target, 'reselect', 4)
        with self.assertRaises(DomainError): self.complete()
        self.decide(target, key='approve-again', revision=5)
        self.act(self.actor, 'issue.update', dict(issue_id=self.issue['id'], title='Changed'), key='requirements', revision=1)
        with self.assertRaises(DomainError): self.complete(revision=2)

    def test_source_write_denial_rolls_back(self):
        from workpal.access.models import SourceGrant
        from workpal.contracts import DomainError
        self.decide(self.ready())
        SourceGrant.objects.filter(user=self.user, source__kind=self.b.kind, source__object_id=self.b.id).update(write=False)
        before = self.snapshot()
        with self.assertRaises(DomainError): self.complete()
        self.assertEqual(before, self.snapshot())

    def test_replay_keeps_history_and_audit_unique(self):
        from workpal.access.service import derive_scope
        from workpal.audit.models import AuditEvent, Outbox
        self.decide(self.ready())
        result = self.complete()
        counts = (IssueTransition.objects.count(), AuditEvent.objects.count(), Outbox.objects.count())
        self.assertEqual(self.complete().data, result.data)
        self.assertEqual(counts, (IssueTransition.objects.count(), AuditEvent.objects.count(), Outbox.objects.count()))
        self.assertIn(self.b, derive_scope(result.object_refs).source_refs)
        self.assertEqual(len(result.object_refs), 3)
        self.assertEqual(result.object_refs[-1], issues.requirement_ref(result.data['requirements_version_id']))

    def test_audit_failure_rolls_back_and_same_key_retries(self):
        from unittest.mock import patch
        from workpal.audit.models import AuditEvent
        self.decide(self.ready())
        before = self.snapshot()
        original = AuditEvent.save
        def fail(event, *args, **kwargs):
            original(event, *args, **kwargs)
            raise RuntimeError('after audit insert')
        with patch.object(AuditEvent, 'save', fail), self.assertRaises(RuntimeError):
            self.complete()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.complete().data['status_category'], 'done')

    def test_history_snapshot_survives_new_decision(self):
        target = self.ready()
        self.decide(target)
        self.complete()
        snapshot = IssueTransition.objects.get(issue_id=self.issue['id']).completion_snapshot
        self.decide(target, key='later-return', revision=3, outcome='request_changes')
        history = self.act(self.actor, 'issue.transitions.list', dict(issue_id=self.issue['id'])).data
        self.assertEqual(history['items'][0]['approval'], snapshot)

    def test_assignee_without_evidence_read_rolls_back(self):
        from django.contrib.auth import get_user_model
        from workpal.identity.models import Membership
        from workpal.contracts import DomainError
        user = get_user_model().objects.create_user(username='completion-assignee')
        Membership.objects.create(user=user, workspace=self.workspace, role='member')
        self.act(self.actor, 'issue.update', dict(issue_id=self.issue['id'], assignee_user_id=user.pk), key='assignee', revision=1)
        self.decide(self.ready())
        before = self.snapshot()
        with self.assertRaises(DomainError): self.complete(revision=2)
        self.assertEqual(before, self.snapshot())

    def test_revocation_blocks_cached_completion(self):
        from workpal.access.models import SourceGrant
        from workpal.contracts import DomainError
        self.decide(self.ready())
        self.complete()
        SourceGrant.objects.filter(user=self.user, source__kind=self.b.kind, source__object_id=self.b.id).update(read=False, write=False)
        with self.assertRaises(DomainError): self.complete()
