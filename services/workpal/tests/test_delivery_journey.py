import hashlib
from dataclasses import asdict
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import Client
from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.audit.models import Outbox
from workpal.identity.models import Membership
from workpal.work.models import IssueTransition


class DeliveryJourney(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()
        self.editor = get_user_model().objects.create(username='editor')
        Membership.objects.create(user=self.editor, workspace=self.workspace, role='member')
        self.clients = {}
        for name, user in (('reviewer', self.user), ('editor', self.editor)):
            for source in (self.a, self.b):
                SourceGrant.objects.create(user=user, source=RegisteredObject.objects.get(
                    kind=source.kind, object_id=source.id), read=True, write=True)
            password = 'Local-test-session-48392!'
            user.set_password(password)
            user.save()
            client = Client(enforce_csrf_checks=True)
            initial = client.get('/api/v1/auth/csrf').json()['csrf_token']
            logged_in = client.post('/api/v1/auth/login', dict(username=user.username, password=password),
                content_type='application/json', HTTP_X_CSRFTOKEN=initial)
            self.assertEqual(logged_in.status_code, 200, logged_in.content)
            self.assertEqual(logged_in.json()['user_id'], user.pk)
            token = client.get('/api/v1/auth/csrf').json()['csrf_token']
            self.clients[name] = (client, token)

    def post(self, path, body, who='reviewer', key=None):
        client, token = self.clients[who]
        return client.post(path, body, content_type='application/json', HTTP_X_CSRFTOKEN=token,
                           HTTP_IDEMPOTENCY_KEY=key or str(uuid4()))

    def send(self, action, payload, who='reviewer', revision=None, key=None, confirmation=None):
        return self.post('/api/v1/actions/' + action, dict(workspace_id=self.workspace.pk,
            payload=payload, expected_revision=revision, idempotency_key=key or str(uuid4()),
            confirmation_id=confirmation), who)

    def perform(self, action, payload, who='reviewer', revision=None, key=None, confirm=False):
        key = key or str(uuid4())
        response = self.send(action, payload, who, revision, key)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        if result['state'] == 'waiting_confirmation':
            self.assertTrue(confirm)
            response = self.send(action, payload, who, revision, key, result['data']['confirmation_id'])
            self.assertEqual(response.status_code, 200, response.content)
            result = response.json()
        self.assertEqual(result['state'], 'completed')
        return result['data']

    def context(self, document=True):
        project = self.perform('project.create', dict(name='Delivery project'))
        if document:
            definition = dict(states=[dict(key='working', label='Working', category='backlog'),
                                      dict(key='accepted', label='Accepted', category='done')],
                transitions=[{'from': 'working', 'to': 'accepted'}],
                review_policy=dict(completion='approved_delivery', reviewer_roles=['owner']))
            draft = self.perform('workflow.create', dict(name='Document approval', definition=definition))
            version = self.perform('workflow.publish', dict(draft_id=draft['id']), revision=1)
            self.perform('project.set_workflow', dict(project_id=project['id'], workflow_version_id=version['id']),
                         revision=1, confirm=True)
        response = self.post(f'/api/v1/workspaces/{self.workspace.pk}/issues', dict(
            project_id=project['id'], title='<img src=x onerror=alert(1)> Document',
            criteria=[dict(key='documented', text='Supply the result document.')],
            assignee_user_id=self.editor.pk, source_refs=[asdict(self.a)]), who='editor')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def upload(self, content):
        upload = self.perform('artifact.upload.begin', dict(filename='evidence.txt', size=len(content),
            media_type='text/plain', source_refs=[asdict(self.b)]), who='editor')
        client, token = self.clients['editor']
        path = f'/api/v1/artifact-uploads/{upload["id"]}/chunks?workspace_id={self.workspace.pk}&offset='
        first = client.put(path + '0', content[:5], content_type='application/octet-stream', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(self.perform('artifact.upload.read', dict(upload_id=upload['id']), who='editor')['offset'], 5)
        failed = self.send('artifact.upload.finish', dict(upload_id=upload['id'], sha256=hashlib.sha256(content).hexdigest()),
                           who='editor', key='finish-' + str(upload['id']))
        self.assertEqual(failed.status_code, 409, failed.content)
        retry = client.put(path + '0', content[:5], content_type='application/octet-stream', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(retry.json()['offset'], 5)
        second = client.put(path + '5', content[5:], content_type='application/octet-stream', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(second.json()['offset'], len(content))
        artifact = self.perform('artifact.upload.finish', dict(upload_id=upload['id'], sha256=hashlib.sha256(content).hexdigest()),
                                who='editor', key='finish-' + str(upload['id']))
        reviewer, _ = self.clients['reviewer']
        pieces = []
        for offset in range(0, len(content), 7):
            response = reviewer.get(f'/api/v1/artifacts/{artifact["id"]}/chunks?workspace_id={self.workspace.pk}&offset={offset}&length=7')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/octet-stream')
            pieces.append(response.content)
        self.assertEqual(b''.join(pieces), content)
        self.assertEqual(hashlib.sha256(b''.join(pieces)).hexdigest(), artifact['sha256'])
        return artifact

    def submit(self, issue, artifact, key, evidence=True):
        body = dict(workspace_id=self.workspace.pk, requirements_revision=issue['requirements_revision'],
            summary='Human supplied ' + key, artifact_ids=[artifact['id']],
            evidence=[dict(criterion_key='documented', artifact_ids=[artifact['id']] if evidence else [],
                           note='Human explanation')])
        response = self.post(f'/api/v1/issues/{issue["id"]}/deliveries', body, 'editor', key)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['source'], 'human')
        return response.json(), body

    def decide(self, target, revision, outcome, who='reviewer'):
        return self.post(f'/api/v1/deliveries/{target["id"]}/reviews', dict(workspace_id=self.workspace.pk,
            revision=revision, version=target['number'], decision=dict(outcome=outcome, reason='Human decision.')), who)

    def test_real_multiuser_upload_rework_review_completion_and_revocation(self):
        issue = self.context()
        subject = dict(type='issue', id=str(issue['id']))
        first_artifact = self.upload(b'First human supplied document.\x00')
        first, _ = self.submit(issue, first_artifact, 'first', evidence=False)
        self.perform('delivery.select_current', dict(delivery_id=first['id'], reason='Inspect first submission'), revision=1)
        self.assertEqual(self.decide(first, 2, 'approve').json()['code'], 'evidence_required')
        rejected = self.decide(first, 2, 'request_changes')
        self.assertEqual(rejected.status_code, 200, rejected.content)
        self.assertEqual(rejected.json()['actor_user_id'], self.user.pk)
        second_artifact = self.upload(b'Second human supplied document with revision.\x00')
        second, second_body = self.submit(issue, second_artifact, 'second')
        self.assertEqual(self.perform('delivery.current.read', dict(subject=subject))['current_delivery_id'], first['id'])
        self.perform('delivery.select_current', dict(delivery_id=second['id'], reason='Review revised document'), revision=3)
        self.assertEqual(self.decide(second, 4, 'approve', who='editor').status_code, 403)
        accepted = self.decide(second, 4, 'approve')
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertEqual(self.perform('issue.read', dict(issue_id=issue['id']))['status_key'], 'working')
        comparison = self.perform('delivery.compare', dict(before_delivery_id=first['id'], after_delivery_id=second['id']), who='editor')
        self.assertEqual(comparison['artifacts']['added'][0]['id'], second_artifact['id'])
        self.assertEqual(comparison['artifacts']['removed'][0]['id'], first_artifact['id'])
        self.assertEqual(len(comparison['evidence']['changed']), 1)
        reviews = self.perform('review.list', dict(subject=subject), who='editor')['items']
        self.assertEqual([r['decision']['outcome'] for r in reviews], ['request_changes', 'approve'])
        approval = self.perform('delivery.approval.read', dict(subject=subject))
        transition_body = dict(workspace_id=self.workspace.pk, revision=1, target='accepted', reason='Checked document')
        transition_url = f'/api/v1/issues/{issue["id"]}/transitions'
        self.assertEqual(self.post(transition_url, transition_body, 'editor').status_code, 403)
        done = self.post(transition_url, transition_body, key='complete')
        self.assertEqual(done.status_code, 200, done.content)
        self.assertEqual(done.json()['status_category'], 'done')
        history = self.perform('issue.transitions.list', dict(issue_id=issue['id']))['items'][0]
        self.assertEqual(history['approval'], approval)
        self.assertEqual(IssueTransition.objects.get(issue_id=issue['id']).completion_review_id, accepted.json()['id'])
        self.perform('issue.archive', dict(issue_id=issue['id']), revision=2)
        self.assertEqual(self.perform('review.read', dict(review_id=accepted.json()['id']))['decision']['outcome'], 'approve')
        SourceGrant.objects.filter(user=self.editor, source__kind=self.b.kind, source__object_id=self.b.id).update(read=False, write=False)
        for action, payload in (
            ('issue.read', dict(issue_id=issue['id'])), ('delivery.read', dict(delivery_id=second['id'])),
            ('review.read', dict(review_id=accepted.json()['id'])), ('delivery.approval.read', dict(subject=subject)),
            ('issue.activity.list', dict(issue_id=issue['id'])),
        ):
            self.assertEqual(self.send(action, payload, who='editor').status_code, 403)
        self.assertEqual(self.post(f'/api/v1/issues/{issue["id"]}/deliveries', second_body, 'editor', 'second').status_code, 403)
        editor, _ = self.clients['editor']
        self.assertEqual(editor.get(f'/api/v1/artifacts/{second_artifact["id"]}/chunks?workspace_id={self.workspace.pk}&offset=0').status_code, 403)
        self.assertEqual(self.perform('issue.list', dict(include_archived=True), who='editor')['items'], [])
        self.assertEqual(self.perform('inbox.list', {}, who='editor')['items'], [])
        self.assertEqual(self.perform('delivery.read', dict(delivery_id=second['id'])), second)
        self.assertFalse(any(action.startswith(('run.', 'runtime.', 'execution.'))
                             for action in Outbox.objects.values_list('action_id', flat=True)))

    def test_default_code_review_remains_in_review_without_provider_merge_evidence(self):
        issue = self.context(document=False)
        for target in ('todo', 'in_progress', 'in_review'):
            issue = self.perform('issue.transition', dict(issue_id=issue['id'], target=target),
                                 who='editor', revision=issue['revision'])
        artifact = self.upload(b'Human report, without tool execution or merge facts.')
        target, _ = self.submit(issue, artifact, 'code-report')
        self.perform('delivery.select_current', dict(delivery_id=target['id'], reason='Inspect human report'), revision=1)
        self.assertEqual(self.decide(target, 2, 'approve').status_code, 200)
        approval = self.perform('delivery.approval.read', dict(subject=dict(type='issue', id=str(issue['id']))))
        self.assertEqual((approval['status'], approval['completion_policy']), ('approved', 'approved_head_merged'))
        response = self.post(f'/api/v1/issues/{issue["id"]}/transitions', dict(workspace_id=self.workspace.pk,
            revision=issue['revision'], target='done', reason='Human approval alone'))
        self.assertEqual((response.status_code, response.json()['code']), (409, 'completion_not_ready'))
        self.assertEqual(self.perform('issue.read', dict(issue_id=issue['id']))['status_key'], 'in_review')
