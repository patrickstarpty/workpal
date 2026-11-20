from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.access.models import RegisteredObject, SourceLink
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError, ObjectRef
from workpal.identity.models import Membership
from workpal.work import issues, transitions, dependencies, service as projects
from workpal.work.models import Issue, IssueRequirements, IssueTransition, IssueDependency
from workpal.workflows import service as workflows


class StateFixtures(AccessFixtures):
    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()
        self.definition = {
            'states': [
                {'key': 'incoming', 'label': 'Done is just a label', 'category': 'backlog'},
                {'key': 'working', 'label': 'Working', 'category': 'in_progress'},
                {'key': 'hold', 'label': 'Hold', 'category': 'blocked'},
                {'key': 'finished', 'label': 'Finished', 'category': 'done'},
                {'key': 'stopped', 'label': 'Stopped', 'category': 'cancelled'},
            ],
            'transitions': [{'from': a, 'to': b} for a, b in (
                ('incoming', 'working'), ('working', 'finished'), ('working', 'hold'),
                ('hold', 'working'), ('working', 'working'), ('working', 'stopped'),
                ('stopped', 'incoming'))],
            'review_policy': {'completion': 'manual', 'reviewer_roles': ['owner']},
        }
        self.project = self.project_for(self.definition)
        self.issue = issues.create(self.actor, self.project['id'], 'Task')

    def project_for(self, definition):
        project = projects.create(self.actor, 'Project')
        draft = workflows.create(self.actor, 'Workflow', definition)
        version = workflows.publish(self.actor, draft['id'], 1)
        return projects.set_workflow(self.actor, project['id'], version['id'], 1)

    def move(self, row, target, key=None, actor=None, **fields):
        return self.act(actor or self.actor, 'issue.transition',
                        {'issue_id': row['id'], 'target': target, **fields},
                        key=key or f"move-{row['id']}-{row['revision']}", revision=row['revision']).data

    def tables(self):
        models = (Issue, IssueRequirements, IssueTransition, IssueDependency, RegisteredObject,
                  SourceLink, IdempotencyResult, AuditEvent, Outbox)
        return {model.__name__: list(model.objects.order_by('pk').values()) for model in models}


class IssueStateReview(StateFixtures, WorkpalCase):
    def test_manual_done_replay_rechecks_human_identity_and_reviewer_role(self):
        row = self.move(self.issue, 'working')
        done = self.move(row, 'finished', key='done', reason='Manually verified')
        before = self.tables()
        agent = Actor(self.user.pk, self.workspace.pk, executor_id='agent-review')
        with self.assertRaises(DomainError) as caught:
            self.move(row, 'finished', key='done', reason='Manually verified', actor=agent)
        self.assertEqual(caught.exception.status, 403)
        self.member.role = 'member'
        self.member.save()
        with self.assertRaises(DomainError) as caught:
            self.move(row, 'finished', key='done', reason='Manually verified')
        self.assertEqual(caught.exception.status, 403)
        self.member.role = 'owner'
        self.member.save()
        self.assertEqual(self.move(row, 'finished', key='done', reason='Manually verified'), done)
        self.assertEqual(self.tables(), before)

    def test_manual_done_requires_human_role_reason_and_does_not_dispatch(self):
        row = self.move(self.issue, 'working')
        before = self.tables()
        with self.assertRaises(DomainError) as caught:
            self.move(row, 'finished', reason='  ')
        self.assertEqual(caught.exception.status, 400)
        agent = Actor(self.user.pk, self.workspace.pk, executor_id='agent-review')
        with self.assertRaises(DomainError) as caught:
            self.move(row, 'finished', reason='Checked', actor=agent)
        self.assertEqual(caught.exception.status, 403)
        self.member.role = 'member'
        self.member.save()
        with self.assertRaises(DomainError) as caught:
            self.move(row, 'finished', reason='Checked')
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.tables(), before)
        self.member.role = 'owner'
        self.member.save()
        done = self.move(row, 'finished', reason='Checked')
        self.assertEqual(done['status_category'], 'done')
        self.assertEqual(done['lifecycle'], 'done')
        self.assertEqual(done['requirements_version_id'], self.issue['requirements_version_id'])
        self.assertEqual(set(Outbox.objects.values_list('action_id', flat=True)), {'issue.transition'})

    def test_unimplemented_evidence_policies_cannot_be_completed_by_client_assertion(self):
        for policy in ('approved_delivery', 'approved_head_merged'):
            definition = deepcopy(self.definition)
            definition['review_policy']['completion'] = policy
            project = self.project_for(definition)
            row = self.move(issues.create(self.actor, project['id'], policy), 'working')
            before = self.tables()
            with self.assertRaises(DomainError) as caught:
                self.move(row, 'finished', reason='Claiming success')
            self.assertEqual(caught.exception.code, 'completion_not_ready')
            with self.assertRaises(DomainError) as caught:
                self.move(row, 'finished', reason='Claiming success', approved=True)
            self.assertEqual(caught.exception.status, 400)
            self.assertEqual(self.tables(), before)

    def test_custom_snapshot_and_history_survive_project_rebind_and_requirement_edit(self):
        projects.set_workflow(self.actor, self.project['id'], 0, self.project['revision'])
        self.assertEqual(self.issue['lifecycle'], 'unstarted')
        row = self.move(self.issue, 'working')
        history = transitions.list_transitions(self.actor, row['id'])['items'][0]
        self.assertEqual(history['from_key'], 'incoming')
        self.assertEqual(history['to_key'], 'working')
        self.assertEqual(history['workflow_sha256'], self.issue['workflow_snapshot']['sha256'])
        self.assertEqual(history['requirements_version_id'], self.issue['requirements_version_id'])
        edited = self.act(self.actor, 'issue.update', {'issue_id': row['id'], 'title': 'New requirement'},
                          key='edit', revision=row['revision']).data
        self.assertEqual(transitions.list_transitions(self.actor, row['id'])['items'][0], history)
        done = self.move(edited, 'finished', reason='Reviewed latest requirements')
        self.assertEqual(done['status_key'], 'finished')
        self.assertEqual(done['workflow_snapshot'], self.issue['workflow_snapshot'])

    def test_block_requires_readable_current_owner_and_retains_reason_on_exit(self):
        row = self.move(self.issue, 'working')
        other = get_user_model().objects.create(username='block-owner')
        Membership.objects.create(user=other, workspace=self.other, role='member')
        before = self.tables()
        for fields in ({'reason': 'Needed'}, {'blocked_owner_user_id': self.user.pk},
                       {'reason': 'Needed', 'blocked_owner_user_id': other.pk}):
            with self.subTest(fields=fields), self.assertRaises(DomainError):
                self.move(row, 'hold', **fields)
        self.assertEqual(self.tables(), before)
        Membership.objects.create(user=other, workspace=self.workspace, role='member')
        self.register(self.workspace.pk, issues.ref(row['id']), [self.a])
        self.grant(self.a, read=True, write=True)
        with self.assertRaises(DomainError):
            self.move(row, 'hold', reason='Needed', blocked_owner_user_id=other.pk)
        blocked = self.move(row, 'hold', reason='Awaiting user decision', blocked_owner_user_id=self.user.pk)
        self.assertEqual(blocked['blocked_reason'], 'Awaiting user decision')
        self.assertEqual(blocked['blocked_owner_user_id'], self.user.pk)
        self.assertEqual(blocked['lifecycle'], 'started')
        unblocked = self.move(blocked, 'working', reason='Decision received')
        self.assertEqual(unblocked['blocked_reason'], '')
        self.assertEqual(unblocked['blocked_owner_user_id'], 0)
        history = transitions.list_transitions(self.actor, row['id'])['items'][-1]
        self.assertEqual(history['before_blocked_reason'], 'Awaiting user decision')
        self.assertEqual(history['before_blocked_owner_id'], self.user.pk)
        self.assertEqual(history['after_blocked_owner_id'], 0)
        self.assertEqual(history['reason'], 'Decision received')

    def test_history_filters_each_record_before_pagination_and_carries_visible_sources(self):
        row = self.move(self.issue, 'working')
        row = self.move(row, 'hold', reason='Waiting', blocked_owner_user_id=self.user.pk)
        row = self.move(row, 'working')
        self.move(row, 'working')
        history = list(IssueTransition.objects.filter(issue_id=row['id']).order_by('pk'))
        self.register(self.workspace.pk, ObjectRef('issue_transition', str(history[0].pk)), [self.a])
        self.register(self.workspace.pk, ObjectRef('issue_transition', str(history[1].pk)), [self.b])
        self.grant(self.b, read=True)
        RegisteredObject.objects.filter(kind='issue_transition', object_id=str(history[2].pk)).update(available=False)
        result = self.act(self.actor, 'issue.transitions.list', {'issue_id': row['id'], 'limit': 1})
        self.assertEqual([item['id'] for item in result.data['items']], [history[1].pk])
        self.assertEqual(result.data['next_cursor'], history[1].pk)
        self.assertIn(ObjectRef('issue_transition', str(history[1].pk)), result.object_refs)
        audit = AuditEvent.objects.filter(action_id='issue.transitions.list').latest('created_at')
        self.assertIn({'kind': self.b.kind, 'id': self.b.id}, audit.scope_refs)
        next_page = self.act(self.actor, 'issue.transitions.list',
                             {'issue_id': row['id'], 'limit': 1, 'cursor': result.data['next_cursor']}).data
        self.assertEqual([item['id'] for item in next_page['items']], [history[3].pk])
        self.assertEqual(next_page['next_cursor'], 0)

    def test_reason_limit_accepts_unicode_characters_and_rejects_invalid_inputs(self):
        row = self.move(self.issue, 'working', reason='说' * 2000)
        for fields in ({'reason': '\ud800'}, {'reason': 'x' * 4001},
                       {'blocked_owner_user_id': True}, {'reason': None}):
            with self.subTest(fields=fields), self.assertRaises(DomainError):
                self.move(row, 'working', **fields)

    def test_late_history_registration_failure_rolls_back_all_owned_tables(self):
        before = self.tables()
        original = transitions.register_object
        def broken(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('after history registration')
        with patch.object(transitions, 'register_object', broken):
            with self.assertRaises(RuntimeError):
                self.move(self.issue, 'working')
        self.assertEqual(self.tables(), before)
        result = self.move(self.issue, 'working')
        self.assertEqual(result['revision'], 2)
        self.assertEqual(IssueTransition.objects.count(), 1)
        self.assertEqual(Outbox.objects.count(), 1)
