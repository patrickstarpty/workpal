from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import connections
from django.test import TransactionTestCase

from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.actions.registry import execute
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, ActionRequest, DomainError, ObjectRef
from workpal.identity.models import Membership
from workpal.workflows import service
from workpal.workflows.contracts import default_definition
from workpal.workflows.models import WorkflowDraft, WorkflowVersion


class WorkflowReviewTests(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()

    def create(self, name='Flow', key='c'):
        return self.act(self.actor, 'workflow.create', {'name': name}, key=key).data

    def test_version_keeps_definition_and_name_after_later_publication(self):
        draft = self.create()
        first = self.act(self.actor, 'workflow.publish', {'draft_id': draft['id']}, key='p1', revision=1).data
        original = deepcopy(first)
        changed = deepcopy(first['definition'])
        changed['states'][0]['label'] = 'New backlog label'
        changed['review_policy']['completion'] = 'approved_delivery'
        self.act(self.actor, 'workflow.update', {'draft_id': draft['id'], 'name': 'New name',
                                                'definition': changed}, key='u', revision=2)
        second = self.act(self.actor, 'workflow.publish', {'draft_id': draft['id']}, key='p2', revision=3).data
        self.assertEqual(second['definition'], changed)
        self.assertNotEqual(second['sha256'], original['sha256'])
        first['definition']['states'].clear()
        self.assertEqual(service.read_version(self.actor, original['id']), original)
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, 'workflow.version.update', {'version_id': original['id']}, key='illegal')
        self.assertEqual(caught.exception.code, 'unknown_action')

    def test_custom_keys_and_rework_cycles_are_valid(self):
        definition = {
            'states': [{'key': 'incoming', 'label': 'Incoming', 'category': 'backlog'},
                       {'key': 'finished', 'label': 'Finished', 'category': 'done'}],
            'transitions': [{'from': 'incoming', 'to': 'finished'}, {'from': 'finished', 'to': 'incoming'}],
            'review_policy': {'completion': 'manual', 'reviewer_roles': ['admin']},
        }
        result = self.act(self.actor, 'workflow.create', {'name': 'Custom', 'definition': definition}, key='c')
        self.assertEqual(result.data['definition'], definition)

    def test_blank_state_label_is_rejected(self):
        definition = default_definition()
        definition['states'][0]['label'] = ' \t '
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, 'workflow.create', {'name': 'Bad', 'definition': definition}, key='bad')
        self.assertEqual(caught.exception.status, 400)
        self.assertFalse(WorkflowDraft.objects.exists())

    def test_source_revoke_restricts_versions_publish_replay_and_pagination(self):
        hidden = self.create()
        self.register(self.workspace.pk, ObjectRef('workflow', str(hidden['id'])), [self.a])
        grant = self.grant(self.a, read=True, write=True, publish=True)
        payload = {'draft_id': hidden['id']}
        version = self.act(self.actor, 'workflow.publish', payload, key='p', revision=1).data
        grant.publish = False
        grant.save()
        self.assertEqual(service.read_version(self.actor, version['id']), version)
        with self.assertRaises(DomainError):
            self.act(self.actor, 'workflow.publish', payload, key='p', revision=1)
        first = self.create('Visible one', key='one')
        last = self.create('Visible two', key='two')
        grant.read = False
        grant.save()
        for action, body, kwargs in (
            ('workflow.read', payload, {}),
            ('workflow.version.read', {'version_id': version['id']}, {}),
            ('workflow.publish', payload, {'key': 'p', 'revision': 1}),
        ):
            with self.subTest(action=action), self.assertRaises(DomainError):
                self.act(self.actor, action, body, **kwargs)
        page = self.act(self.actor, 'workflow.list', {'limit': 1}).data
        self.assertEqual([row['id'] for row in page['items']], [first['id']])
        self.assertEqual(page['next_cursor'], first['id'])
        self.assertEqual(set(page), {'items', 'next_cursor'})
        page = self.act(self.actor, 'workflow.list', {'limit': 1, 'cursor': page['next_cursor']}).data
        self.assertEqual([row['id'] for row in page['items']], [last['id']])
        self.assertEqual(page['next_cursor'], 0)

    def test_workspace_and_member_management_boundaries(self):
        draft = self.create()
        version = self.act(self.actor, 'workflow.publish', {'draft_id': draft['id']}, key='p', revision=1).data
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        foreign = Actor(self.user.pk, self.other.pk)
        for action, payload in (('workflow.read', {'draft_id': draft['id']}),
                                ('workflow.version.read', {'version_id': version['id']})):
            with self.assertRaises(DomainError) as caught:
                self.act(foreign, action, payload)
            self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.act(foreign, 'workflow.list', {}).data, {'items': [], 'next_cursor': 0})
        self.member.role = 'member'
        self.member.save()
        self.assertEqual(service.read_version(self.actor, version['id']), version)
        for action, payload in (('workflow.create', {'name': 'Forbidden'}),
                                ('workflow.update', {'draft_id': draft['id'], 'name': 'Forbidden'}),
                                ('workflow.publish', {'draft_id': draft['id']})):
            with self.assertRaises(DomainError) as caught:
                self.act(self.actor, action, payload, key='forbidden', revision=2)
            self.assertEqual(caught.exception.status, 403)

    def test_late_publication_failure_rolls_back_and_can_retry(self):
        draft = self.create()
        payload = {'draft_id': draft['id']}
        with patch.object(service, 'register_object', side_effect=RuntimeError('late failure')):
            with self.assertRaises(RuntimeError):
                self.act(self.actor, 'workflow.publish', payload, key='p', revision=1)
        current = WorkflowDraft.objects.get(pk=draft['id'])
        self.assertEqual(current.revision, 1)
        self.assertIsNone(current.current_version_id)
        self.assertFalse(WorkflowVersion.objects.exists())
        self.assertFalse(IdempotencyResult.objects.filter(action_id='workflow.publish').exists())
        self.assertFalse(Outbox.objects.filter(action_id='workflow.publish').exists())
        self.assertFalse(AuditEvent.objects.filter(action_id='workflow.publish').exists())
        result = self.act(self.actor, 'workflow.publish', payload, key='p', revision=1)
        self.assertEqual(result.data['number'], 1)
        self.assertEqual(Outbox.objects.filter(action_id='workflow.publish').count(), 1)


class ConcurrentWorkflowPublication(AccessFixtures, TransactionTestCase):
    def exercise(self, keys):
        self.member.role = 'owner'
        self.member.save()
        draft = execute(self.actor, ActionRequest('workflow.create', {'name': 'Race'}, None, 'c')).data
        barrier = Barrier(2)
        def publish(key):
            connections.close_all()
            try:
                connection = connections['default']
                connection.ensure_connection()
                connection_id = id(connection.connection)
                barrier.wait(timeout=10)
                try:
                    result = execute(self.actor, ActionRequest('workflow.publish', {'draft_id': draft['id']}, 1, key))
                    return connection_id, result.state, result.data
                except DomainError as error:
                    return connection_id, error.code, error.status
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(publish, keys))
        self.assertEqual(len({r[0] for r in results}), 2)
        self.assertEqual(WorkflowVersion.objects.count(), 1)
        self.assertEqual(WorkflowDraft.objects.get(pk=draft['id']).revision, 2)
        self.assertEqual(AuditEvent.objects.filter(action_id='workflow.publish').count(), 1)
        self.assertEqual(Outbox.objects.filter(action_id='workflow.publish').count(), 1)
        return results

    def test_same_revision_different_keys_have_one_winner(self):
        results = self.exercise(['first', 'second'])
        self.assertCountEqual([r[1] for r in results], ['completed', 'revision_conflict'])

    def test_same_key_replays_one_publication(self):
        results = self.exercise(['same', 'same'])
        self.assertEqual(results[0][1:], results[1][1:])
        self.assertEqual(results[0][1], 'completed')
