from copy import deepcopy
from dataclasses import asdict
from unittest.mock import patch

from django.db.models.deletion import ProtectedError
from tests.support import WorkpalCase
from tests.test_review_validation import ReviewFixtures
from workpal.access.models import SourceGrant
from workpal.access.service import derive_scope
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError, ObjectRef, SubjectRef
from workpal.delivery import approval, review, service
from workpal.delivery.models import Delivery, Review
from workpal.identity.models import Membership
from workpal.work import issues, transitions, dependencies, service as projects
from workpal.work.models import IssueTransition
from workpal.workflows import service as workflows


class CompletionFixtures(ReviewFixtures):
    def setUp(self):
        super().setUp()
        self.configure()

    def configure(self, policy='approved_delivery', roles=None):
        definition = dict(states=[dict(key='start', label='Start', category='backlog'),
                                  dict(key='finished', label='Finished', category='done')],
            transitions=[{'from': 'start', 'to': 'finished'}, {'from': 'finished', 'to': 'start'}],
            review_policy=dict(completion=policy, reviewer_roles=roles or ['owner']))
        self.project = projects.create(self.actor, 'Completion')
        draft = workflows.create(self.actor, 'Completion workflow', definition)
        version = workflows.publish(self.actor, draft['id'], 1)
        projects.set_workflow(self.actor, self.project['id'], version['id'], 1)
        self.issue = issues.create(self.actor, self.project['id'], 'Complete this work',
            criteria=[dict(key='documented', text='Provide a document.')], source_refs=[asdict(self.a)])
        self.subject = dict(type='issue', id=str(self.issue['id']))

    def approved(self, **extra):
        artifact = self.published_artifact()
        key = 'target-' + str(self.issue['id'])
        target = self.submit(key, artifact_ids=[artifact['id']],
            evidence=[dict(criterion_key='documented', artifact_ids=[artifact['id']])])
        self.choose(target, 'select-' + key, 1)
        saved = self.decide(target, key='review-' + key, **extra).data
        return target, saved

    def complete(self, key='complete', revision=1, actor=None, **extra):
        return self.act(actor or self.actor, 'issue.transition', dict(issue_id=self.issue['id'],
            target='finished', **dict(dict(reason='Accepted'), **extra)), key=key, revision=revision)


class CompletionReview(CompletionFixtures, WorkpalCase):
    def test_manual_needs_no_review_but_code_policy_still_requires_merge_facts(self):
        self.configure('manual')
        result = self.complete(key='manual')
        event = IssueTransition.objects.get(issue_id=self.issue['id'])
        self.assertEqual(result.data['status_category'], 'done')
        self.assertEqual(result.object_refs, [issues.ref(self.issue['id']), issues.requirement_ref(result.data['requirements_version_id'])])
        self.assertIsNone(event.completion_review_id)
        self.assertEqual(event.completion_snapshot, {})
        self.assertNotIn('approval', transitions.list_transitions(self.actor, self.issue['id'])['items'][0])
        self.configure('approved_head_merged')
        self.approved()
        self.assertEqual(approval.inspect(self.actor, SubjectRef(**self.subject))[0]['status'], 'approved')
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.complete(key='code')
        self.assertEqual(caught.exception.code, 'completion_not_ready')
        self.assertEqual(self.snapshot(), before)

    def test_human_role_reason_closed_input_and_dependencies_still_gate_approved_work(self):
        self.approved()
        before = self.snapshot()
        executor = Actor(self.user.pk, self.workspace.pk, executor_id='agent')
        with self.assertRaises(DomainError) as caught:
            self.complete(actor=executor)
        self.assertEqual(caught.exception.status, 403)
        for role in ('member', 'admin'):
            self.member.role = role
            self.member.save()
            with self.assertRaises(DomainError) as caught:
                self.complete()
            self.assertEqual(caught.exception.status, 403)
        self.member.role = 'owner'
        self.member.save()
        for extra in (dict(reason=' '), dict(approved=True), dict(review_id=1), dict(completion_snapshot={})):
            with self.assertRaises(DomainError) as caught:
                self.complete(**extra)
            self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.snapshot(), before)
        dependency = issues.create(self.actor, self.project['id'], 'Unfinished dependency')
        dependencies.add(self.actor, self.issue['id'], dependency['id'], 1)
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.complete(revision=2)
        self.assertEqual(caught.exception.code, 'dependency_blocked')
        self.assertEqual(self.snapshot(), before)
        dependencies.remove(self.actor, self.issue['id'], dependency['id'], 2)
        self.assertEqual(self.complete(revision=3).data['status_category'], 'done')

    def test_member_reviewer_snapshot_applies_without_owner_override(self):
        self.configure(roles=['member'])
        self.member.role = 'member'
        self.member.save()
        self.approved()
        self.member.role = 'owner'
        self.member.save()
        with self.assertRaises(DomainError) as caught:
            self.complete()
        self.assertEqual(caught.exception.status, 403)
        self.member.role = 'member'
        self.member.save()
        self.assertEqual(self.complete().data['status_category'], 'done')

    def test_exact_sources_protect_issue_history_existing_comments_and_replay_without_a_cycle(self):
        private = self.register(self.workspace.pk, ObjectRef('source', 'private-decision'), is_source=True)
        grant = self.grant(private, read=True, write=True)
        target, saved = self.approved(source_refs=[asdict(private)])
        comment = self.act(self.actor, 'comment.create', dict(issue_id=self.issue['id'], body='Before completion'), key='comment').data
        self.assertEqual(derive_scope([issues.ref(self.issue['id'])]).source_refs, {self.a})
        grant.write = False
        grant.save()
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.complete()
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
        grant.write = True
        grant.save()
        result = self.complete()
        history = IssueTransition.objects.get(issue_id=self.issue['id'])
        roots = {self.a, self.b, private}
        self.assertEqual(result.object_refs, [issues.ref(self.issue['id']), transitions.ref(history.pk), issues.requirement_ref(result.data['requirements_version_id'])])
        for ref in (issues.ref(self.issue['id']), transitions.ref(history.pk),
                    ObjectRef('comment', str(comment['id'])), service.ref(target['id']), review.ref(saved['id'])):
            self.assertEqual(derive_scope([ref]).source_refs, roots)
        self.assertEqual(derive_scope([ObjectRef('artifact', str(target['artifacts_snapshot'][0]['id']))]).source_refs, {self.b})
        event = AuditEvent.objects.get(action_id='issue.transition')
        self.assertEqual({ObjectRef(**r) for r in event.scope_refs}, roots | set(result.object_refs))
        self.assertEqual(Outbox.objects.get(event=event).scope_refs, event.scope_refs)
        self.assertEqual(IdempotencyResult.objects.get(action_id='issue.transition').scope_refs, event.scope_refs)
        grant.read = False
        grant.save()
        before = self.snapshot()
        for call in (lambda: issues.read(self.actor, self.issue['id']),
                     lambda: self.act(self.actor, 'comment.read', dict(comment_id=comment['id'])),
                     lambda: transitions.list_transitions(self.actor, self.issue['id']), self.complete):
            with self.assertRaises(DomainError) as caught:
                call()
            self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)

    def test_real_fk_and_historical_snapshot_survive_requirements_and_current_decision_changes(self):
        target, saved = self.approved()
        result = self.complete()
        event = IssueTransition.objects.get(issue_id=self.issue['id'])
        proof = deepcopy(event.completion_snapshot)
        for row in (Review.objects.get(pk=saved['id']), Delivery.objects.get(pk=target['id'])):
            with self.assertRaises(ProtectedError):
                row.delete()
        issues.update(self.actor, self.issue['id'], 2, title='Later requirements')
        self.decide(target, key='later-review', revision=3, outcome='request_changes')
        before = self.snapshot()
        replay = self.complete()
        self.assertEqual((replay.data, replay.object_refs), (result.data, result.object_refs))
        self.assertEqual(self.snapshot(), before)
        history = self.act(self.actor, 'issue.transitions.list', dict(issue_id=self.issue['id'])).data['items'][0]
        self.assertEqual(history['approval'], proof)
        history['approval']['subject']['id'] = '999'
        self.assertEqual(transitions.list_transitions(self.actor, self.issue['id'])['items'][0]['approval'], proof)
        self.assertEqual(approval.inspect(self.actor, SubjectRef(**self.subject))[0]['reason'], 'changes_requested')

    def test_late_failure_matrix_rolls_back_sources_history_proof_audit_and_cache(self):
        self.approved()
        before = self.snapshot()
        original_registration = transitions.register_object
        for stage in ('issue_sources', 'history_sources', 'history_insert', 'cache_insert', 'authorization'):
            if stage in ('issue_sources', 'history_sources'):
                kind = 'issue' if stage == 'issue_sources' else 'issue_transition'
                def broken(*args, **kwargs):
                    result = original_registration(*args, **kwargs)
                    if args[1].kind == kind:
                        raise DomainError('storage_unavailable', 'Retry later.', status=503)
                    return result
                owner, name = transitions, 'register_object'
            elif stage == 'authorization':
                owner, name = approval, 'authorize'
                original = approval.authorize
                def broken(*args, **kwargs):
                    original(*args, **kwargs)
                    raise DomainError('storage_unavailable', 'Retry later.', status=503)
            else:
                owner = IssueTransition.objects if stage == 'history_insert' else IdempotencyResult.objects
                name = 'create'
                original = owner.create
                def broken(*args, **kwargs):
                    original(*args, **kwargs)
                    raise DomainError('storage_unavailable', 'Retry later.', status=503)
            with self.subTest(stage=stage), patch.object(owner, name, broken), self.assertRaises(DomainError) as caught:
                self.complete()
            self.assertEqual(caught.exception.status, 503)
            self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.complete().data['status_category'], 'done')
        self.assertEqual(IssueTransition.objects.filter(issue_id=self.issue['id']).count(), 1)

    def test_source_cycle_and_cross_workspace_fail_without_partial_completion(self):
        private = self.register(self.workspace.pk, ObjectRef('source', 'issue-dependent-root'),
                                [issues.ref(self.issue['id'])], is_source=True)
        self.grant(private, read=True, write=True)
        self.approved(source_refs=[asdict(private)])
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.complete()
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(derive_scope([issues.ref(self.issue['id'])]).source_refs, {self.a})
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        foreign = Actor(self.user.pk, self.other.pk)
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.complete(actor=foreign)
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.snapshot(), before)
