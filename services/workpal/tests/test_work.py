import json
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import Client
from tests.support import WorkpalCase
from tests.test_issue_state_review import StateFixtures
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.audit.models import Outbox
from workpal.identity.models import Membership
from workpal.work import service as projects


class WorkIntegration(StateFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.grant(self.a, read=True, write=True, publish=True)
        self.register(self.workspace.pk, projects.ref(self.project['id']), [self.a])
        self.reader = get_user_model().objects.create(username='collaborator')
        Membership.objects.create(user=self.reader, workspace=self.workspace, role='member')
        self.reader_grant = SourceGrant.objects.create(user=self.reader,
            source=RegisteredObject.objects.get(kind=self.a.kind, object_id=self.a.id), read=True, write=True)
        self.clients = {}
        for name, user in (('owner', self.user), ('reader', self.reader)):
            client = Client(enforce_csrf_checks=True)
            client.force_login(user)
            token = client.get('/api/v1/auth/csrf').json()['csrf_token']
            self.clients[name] = (client, token)

    def send(self, action, payload, who='owner', revision=None, key=None, confirmation_id=None):
        client, token = self.clients[who]
        body = {'workspace_id': self.workspace.pk, 'payload': payload, 'expected_revision': revision,
                'idempotency_key': key, 'confirmation_id': confirmation_id}
        return client.post('/api/v1/actions/' + action, json.dumps(body), content_type='application/json',
                           HTTP_X_CSRFTOKEN=token)

    def perform(self, action, payload, who='owner', revision=None, key=None, confirm=False):
        key = key or str(uuid4())
        response = self.send(action, payload, who, revision, key)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        if result['state'] == 'waiting_confirmation':
            self.assertTrue(confirm, 'The test must explicitly approve this operation.')
            response = self.send(action, payload, who, revision, key, result['data']['confirmation_id'])
            self.assertEqual(response.status_code, 200, response.content)
            result = response.json()
        self.assertEqual(result['state'], 'completed')
        return result['data']

    def move_http(self, issue, target, **fields):
        return self.perform('issue.transition', {'issue_id': issue['id'], 'target': target, **fields},
                            revision=issue['revision'])

    def test_multiuser_work_journey_keeps_requirements_notifications_and_states_independent(self):
        project = self.perform('project.update', {'project_id': self.project['id'], 'name': self.project['name'],
                                                'description': 'Repository context'},
                               revision=self.project['revision'])
        other = self.perform('project.create', {'name': project['name'], 'description': 'Other context'})
        matches = self.perform('project.list', {'query': project['name']})['items']
        self.assertEqual({item['id'] for item in matches}, {project['id'], other['id']})
        resource = self.perform('resource.create', {'project_id': project['id'], 'label': 'Repository',
            'provider': 'github', 'repository_ref': 'org/repository', 'checkout_ref': 'main'})
        self.assertEqual(resource['verification_status'], 'unverified')
        self.assertEqual(self.perform('project.read', {'project_id': project['id']})['description'], 'Repository context')
        criteria = [{'key': 'record', 'text': 'Preserve the record'}]
        parent = self.perform('issue.create', {'project_id': project['id'], 'title': 'Parent',
            'criteria': criteria, 'assignee_user_id': self.reader.pk})
        child = self.perform('issue.create', {'project_id': project['id'], 'title': 'Child', 'parent_issue_id': parent['id']})
        dependency = self.perform('issue.create', {'project_id': project['id'], 'title': 'Dependency'})
        original_snapshot = parent['workflow_snapshot']
        parent = self.perform('issue.dependency.add', {'issue_id': parent['id'], 'depends_on_id': dependency['id']},
                              revision=parent['revision'])
        self.perform('issue.subscribe', {'issue_id': parent['id']}, who='reader')
        comment = self.perform('comment.create', {'issue_id': parent['id'], 'body': 'Please check',
                               'mention_user_ids': [self.reader.pk]})
        parent = self.perform('issue.update', {'issue_id': parent['id'], 'title': 'Parent v2',
            'criteria': [{'key': 'record', 'text': 'Preserve the record and history'}]}, revision=parent['revision'])
        requirements_id = parent['requirements_version_id']
        parent = self.move_http(parent, 'working')
        parent = self.move_http(parent, 'hold', reason='Need a decision', blocked_owner_user_id=self.reader.pk)
        notices = self.perform('inbox.list', {}, who='reader')['items']
        self.assertEqual({notice['kind'] for notice in notices}, {'assignment', 'mention', 'blocked'})
        for notice in notices:
            self.perform('inbox.mark_read', {'notification_id': notice['id']}, who='reader', revision=notice['revision'])
        self.assertEqual(self.perform('issue.read', {'issue_id': parent['id']}), parent)
        self.assertEqual(self.perform('inbox.list', {'unread_only': True}, who='reader')['items'], [])
        parent = self.move_http(parent, 'working', reason='Decision received')
        child = self.move_http(child, 'working')
        child = self.move_http(child, 'finished', reason='Child checked')
        self.assertEqual(self.perform('issue.read', {'issue_id': parent['id']})['status_key'], 'working')
        response = self.send('issue.transition', {'issue_id': parent['id'], 'target': 'finished', 'reason': 'Check'},
                             revision=parent['revision'], key='blocked-by-dependency')
        self.assertEqual((response.status_code, response.json()['code']), (409, 'dependency_blocked'))
        dependency = self.move_http(dependency, 'working')
        self.move_http(dependency, 'finished', reason='Dependency checked')
        self.perform('project.set_workflow', {'project_id': project['id'], 'workflow_version_id': 0},
                     revision=project['revision'], confirm=True)
        parent = self.perform('issue.archive', {'issue_id': parent['id']}, revision=parent['revision'])
        self.assertNotIn(parent['id'], [row['id'] for row in self.perform('issue.list', {})['items']])
        self.assertEqual(self.perform('comment.read', {'comment_id': comment['id']}), comment)
        self.assertEqual(self.perform('issue.requirements.read', {'issue_id': parent['id'], 'number': 1})['criteria'], criteria)
        self.assertEqual(parent['workflow_snapshot'], original_snapshot)
        self.assertEqual(parent['requirements_version_id'], requirements_id)
        self.assertEqual(self.perform('issue.read', {'issue_id': child['id']})['archived'], False)
        self.assertEqual(len(self.perform('inbox.list', {}, who='reader')['items']), 3)
        activity = self.perform('issue.activity.list', {'issue_id': parent['id']})['items']
        self.assertIn('comment.create', [event['action_id'] for event in activity])
        self.assertIn('issue.archive', [event['action_id'] for event in activity])
        parent = self.perform('issue.restore', {'issue_id': parent['id']}, revision=parent['revision'])
        self.assertEqual(self.move_http(parent, 'finished', reason='Parent checked')['status_category'], 'done')
        self.assertLessEqual(set(Outbox.objects.values_list('action_id', flat=True)), {
            'project.create', 'project.update', 'project.set_workflow', 'resource.create', 'issue.create',
            'issue.dependency.add', 'issue.update', 'issue.subscribe', 'comment.create', 'issue.transition',
            'inbox.mark_read', 'issue.archive', 'issue.restore'})

    def test_source_revocation_closes_issue_comment_activity_and_inbox_access_together(self):
        issue = self.perform('issue.create', {'project_id': self.project['id'], 'title': 'Restricted title',
                                            'assignee_user_id': self.reader.pk})
        comment = self.perform('comment.create', {'issue_id': issue['id'], 'body': 'Restricted comment',
                                                'mention_user_ids': [self.reader.pk]})
        self.assertEqual(self.perform('issue.read', {'issue_id': issue['id']}, who='reader')['id'], issue['id'])
        self.assertEqual(len(self.perform('issue.activity.list', {'issue_id': issue['id']}, who='reader')['items']), 2)
        notice = self.perform('inbox.list', {}, who='reader')['items'][0]
        self.perform('inbox.mark_read', {'notification_id': notice['id']}, who='reader', key='read', revision=1)
        self.reader_grant.read = False
        self.reader_grant.save()
        for action, payload, revision, key in (
            ('issue.read', {'issue_id': issue['id']}, None, None),
            ('comment.read', {'comment_id': comment['id']}, None, None),
            ('issue.activity.list', {'issue_id': issue['id']}, None, None),
            ('issue.children.list', {'issue_id': issue['id']}, None, None),
            ('inbox.mark_read', {'notification_id': notice['id']}, 1, 'read')):
            response = self.send(action, payload, 'reader', revision, key)
            self.assertEqual(response.status_code, 403, response.content)
            self.assertNotIn(b'Restricted', response.content)
        self.assertEqual(self.perform('issue.list', {}, who='reader')['items'], [])
        self.assertEqual(self.perform('inbox.list', {}, who='reader')['items'], [])
        self.assertEqual(self.perform('issue.read', {'issue_id': issue['id']}), issue)
