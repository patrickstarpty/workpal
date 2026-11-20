import json
from unittest.mock import patch

from django.apps import apps
from django.test import Client
from tests.support import WorkpalCase
from tests.test_issue_state_review import StateFixtures
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor
from workpal.identity.models import Membership
from workpal.work import issues, transitions, service as projects
from workpal.work.models import Issue, IssueRequirements, IssueTransition


class IssueAliasReview(StateFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.csrf = self.client.get('/api/v1/auth/csrf').json()['csrf_token']

    def snapshot(self):
        return {m._meta.label: list(m.objects.order_by('pk').values()) for m in apps.get_models()}

    def post(self, path, payload, key='key', content_type='application/json', raw=False, **headers):
        headers.setdefault('HTTP_X_CSRFTOKEN', self.csrf)
        headers.setdefault('HTTP_IDEMPOTENCY_KEY', key)
        return self.client.post(path, payload if raw else json.dumps(payload), content_type=content_type, **headers)

    def create(self, payload, generic=False, key='create', workspace=None, **headers):
        workspace = self.workspace.pk if workspace is None else workspace
        if generic:
            return self.post('/api/v1/actions/issue.create',
                             {'workspace_id': workspace, 'payload': payload, 'idempotency_key': key}, **headers)
        return self.post(f'/api/v1/workspaces/{workspace}/issues', payload, key=key, **headers)

    def transition(self, row, fields, generic=False, key='transition', workspace=None, **headers):
        workspace = self.workspace.pk if workspace is None else workspace
        if generic:
            return self.post('/api/v1/actions/issue.transition',
                {'workspace_id': workspace, 'payload': {'issue_id': row['id'], **fields},
                 'expected_revision': row['revision'], 'idempotency_key': key}, **headers)
        return self.post(f"/api/v1/issues/{row['id']}/transitions",
                         {'workspace_id': workspace, 'revision': row['revision'], **fields}, key=key, **headers)

    def data(self, response, generic=False):
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['data'] if generic else response.json()

    def test_creation_replays_both_directions_with_one_requirements_and_event_each(self):
        for generic in (True, False):
            payload = {'project_id': self.project['id'], 'title': f'Created {generic}'}
            key = f'create-{generic}'
            first = self.data(self.create(payload, generic, key), generic)
            replay = self.data(self.create(payload, not generic, key), not generic)
            self.assertEqual(first, replay)
            self.assertEqual(first['revision'], 1)
            self.assertEqual(IssueRequirements.objects.filter(issue_id=first['id']).count(), 1)
            for entry in (True, False):
                conflict = self.create({**payload, 'title': 'Different'}, entry, key)
                self.assertEqual((conflict.status_code, conflict.json()['code']), (409, 'idempotency_conflict'))
        self.assertEqual(Issue.objects.count(), 3)
        self.assertEqual(IssueTransition.objects.count(), 0)
        self.assertEqual((AuditEvent.objects.count(), Outbox.objects.count(), IdempotencyResult.objects.count()), (2, 2, 2))

    def test_transitions_replay_both_directions_with_one_history_and_event_each(self):
        working = self.data(self.transition(self.issue, {'target': 'working'}, True), True)
        self.assertEqual(self.data(self.transition(self.issue, {'target': 'working'})), working)
        fields = {'target': 'hold', 'reason': 'Decision needed', 'blocked_owner_user_id': self.user.pk}
        blocked = self.data(self.transition(working, fields, key='block'))
        self.assertEqual(self.data(self.transition(working, fields, True, key='block'), True), blocked)
        self.assertEqual(blocked['revision'], 3)
        history = list(IssueTransition.objects.order_by('revision'))
        self.assertEqual([(h.from_key, h.to_key, h.revision) for h in history],
                         [('incoming', 'working', 2), ('working', 'hold', 3)])
        self.assertTrue(all(h.requirements_version_id == self.issue['requirements_version_id'] and
                            h.actor_executor_id is None for h in history))
        self.assertEqual((AuditEvent.objects.count(), Outbox.objects.count(), IdempotencyResult.objects.count()), (2, 2, 2))
        before = self.snapshot()
        for generic in (False, True):
            response = self.transition(working, {**fields, 'reason': 'Different'}, generic, key='block')
            self.assertEqual(response.status_code, 409)
            response = self.transition(self.issue, {'target': 'working'}, generic, key='stale')
            self.assertEqual((response.status_code, response.json()['code']), (409, 'revision_conflict'))
        self.assertEqual(self.snapshot(), before)

    def test_create_and_transition_replays_require_all_current_source_write_grants(self):
        first = self.grant(self.a, read=True, write=False)
        second = self.grant(self.b, read=True, write=False)
        self.register(self.workspace.pk, projects.ref(self.project['id']), [self.a])
        self.register(self.workspace.pk, issues.ref(self.issue['id']), [self.b])
        self.member.role = 'member'
        self.member.save()
        payload = {'project_id': self.project['id'], 'title': 'Child', 'parent_issue_id': self.issue['id']}
        for grant in (first, second):
            for generic in (False, True):
                response = self.create(payload, generic)
                self.assertEqual(response.status_code, 403, response.content)
            grant.write = True
            grant.save()
        created = self.data(self.create(payload))
        moved = self.data(self.transition(created, {'target': 'working'}, True), True)
        self.assertEqual(moved['revision'], 2)
        second.write = False
        second.save()
        before = self.snapshot()
        for generic in (False, True):
            self.assertEqual(self.create(payload, generic).status_code, 403)
            self.assertEqual(self.transition(created, {'target': 'working'}, generic).status_code, 403)
        self.assertEqual(self.snapshot(), before)

    def test_cross_workspace_objects_are_rejected_even_for_a_shared_owner(self):
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        other_actor = Actor(self.user.pk, self.other.pk)
        other_project = projects.create(other_actor, 'Other')
        other_issue = issues.create(other_actor, other_project['id'], 'Other')
        before = self.snapshot()
        for generic in (False, True):
            calls = (self.create({'project_id': other_project['id'], 'title': 'Wrong'}, generic),
                     self.create({'project_id': self.project['id'], 'title': 'Wrong'}, generic, workspace=self.other.pk),
                     self.transition(self.issue, {'target': 'working'}, generic, workspace=self.other.pk),
                     self.transition(other_issue, {'target': 'todo'}, generic))
            for response in calls:
                self.assertEqual((response.status_code, response.json()['code']), (404, 'not_found'))
        self.assertEqual(self.snapshot(), before)
        created = self.data(self.create({'project_id': other_project['id'], 'title': 'Allowed'}, workspace=self.other.pk))
        self.assertEqual(created['project_id'], other_project['id'])

    def test_manual_done_requires_reason_and_current_human_reviewer_role_even_on_replay(self):
        self.assertEqual(self.transition(self.issue, {'target': 'finished', 'reason': 'Wrong edge'}).status_code, 409)
        working = self.data(self.transition(self.issue, {'target': 'working'}, key='start'))
        fields = {'target': 'finished', 'reason': 'Verified manually'}
        before = self.snapshot()
        for generic in (False, True):
            self.assertEqual(self.transition(working, {'target': 'finished', 'reason': '   '}, generic).status_code, 400)
            self.assertEqual(self.transition(working, {**fields, 'executor_id': None}, generic).status_code, 400)
        self.assertEqual(self.snapshot(), before)
        self.member.role = 'member'
        self.member.save()
        for generic in (False, True):
            self.assertEqual(self.transition(working, fields, generic).status_code, 403)
        self.member.role = 'owner'
        self.member.save()
        done = self.data(self.transition(working, fields, True), True)
        self.assertEqual(done['status_category'], 'done')
        self.assertEqual(self.data(self.transition(working, fields)), done)
        self.member.role = 'member'
        self.member.save()
        before = self.snapshot()
        for generic in (False, True):
            self.assertEqual(self.transition(working, fields, generic).status_code, 403)
        self.assertEqual(self.snapshot(), before)

    def test_builtin_completion_policy_still_requires_real_delivery_and_merge_facts(self):
        project = projects.create(self.actor, 'Default policy')
        row = self.data(self.create({'project_id': project['id'], 'title': 'Code task'}))
        for target in ('todo', 'in_progress', 'in_review'):
            row = self.data(self.transition(row, {'target': target}, key=target))
        before = self.snapshot()
        for generic in (False, True):
            response = self.transition(row, {'target': 'done', 'reason': 'Claimed complete'}, generic)
            self.assertEqual((response.status_code, response.json()['code']), (409, 'completion_not_ready'))
        self.assertEqual(self.snapshot(), before)

    def test_transport_validation_rejects_invalid_input_without_business_effects(self):
        creation_url = f'/api/v1/workspaces/{self.workspace.pk}/issues'
        transition_url = f"/api/v1/issues/{self.issue['id']}/transitions"
        creation = {'project_id': self.project['id'], 'title': 'New'}
        transition = {'workspace_id': self.workspace.pk, 'revision': 1, 'target': 'working'}
        before = self.snapshot()
        for url, payload in ((creation_url, creation), (transition_url, transition)):
            for body in (None, [], {}, {**payload, 'actor_user_id': self.user.pk}, {**payload, 'idempotency_key': 'body'}):
                self.assertEqual(self.post(url, body).status_code, 400)
            for headers in ({'HTTP_IDEMPOTENCY_KEY': ''}, {'HTTP_IDEMPOTENCY_KEY': 'x' * 201}, {'HTTP_X_CONFIRMATION_ID': ''}):
                self.assertEqual(self.post(url, payload, **headers).status_code, 400)
            self.assertEqual(self.post(url, payload, HTTP_X_CONFIRMATION_ID='not-applicable').status_code, 409)
            self.assertEqual(self.post(url + '?x=1', payload).status_code, 400)
            self.assertEqual(self.post(url, payload, content_type='text/plain').status_code, 400)
            for raw in ('null', '{', '{"target":"working","target":"hold"}', '{"number":Infinity}', '{"text":"\\ud800"}'):
                self.assertEqual(self.post(url, raw, raw=True).status_code, 400)
            with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=2 * 1024 * 1024):
                self.assertEqual(self.post(url, {**payload, 'oversized': 'x' * (1024 * 1024)}).status_code, 413)
        for field in ('workspace_id', 'revision'):
            for value in (True, 0, -1, 2**63, '1', None):
                self.assertEqual(self.post(transition_url, {**transition, field: value}).status_code, 400)
        self.assertEqual(self.post(transition_url, {**transition, 'issue_id': self.issue['id']}).status_code, 400)
        for identifier in (0, 2**63):
            self.assertEqual(self.post(f'/api/v1/workspaces/{identifier}/issues', creation).status_code, 400)
            self.assertEqual(self.post(f'/api/v1/issues/{identifier}/transitions', transition).status_code, 400)
        self.assertEqual(self.snapshot(), before)

    def test_host_csrf_inactive_and_anonymous_checks_with_valid_token_controls(self):
        payload = {'project_id': self.project['id'], 'title': 'New'}
        calls = (lambda **headers: self.create(payload, **headers),
                 lambda **headers: self.transition(self.issue, {'target': 'working'}, **headers))
        for call in calls:
            response = call(HTTP_HOST='evil.invalid')
            self.assertEqual((response.status_code, response.json()['code']), (400, 'invalid_host'))
            self.assertEqual(call(HTTP_X_CSRFTOKEN='').status_code, 403)
        self.user.is_active = False
        self.user.save()
        for call in calls:
            response = call()
            self.assertEqual((response.status_code, response.json()['code']), (403, 'authentication_required'))
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        self.csrf = self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.assertEqual(calls[0]().status_code, 200)
        self.assertEqual(calls[1]().status_code, 200)
        self.client.logout()
        self.csrf = self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        for call in calls:
            response = call()
            self.assertEqual((response.status_code, response.json()['code']), (403, 'authentication_required'))

    def test_late_audit_failure_rolls_back_state_history_notification_and_retry_key(self):
        working = transitions.transition(self.actor, self.issue['id'], 'working', 1)
        fields = {'target': 'hold', 'reason': 'Decision', 'blocked_owner_user_id': self.user.pk}
        original = registry.record
        def fail_after_audit(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('private database details')
        before = self.snapshot()
        with patch.object(registry, 'record', fail_after_audit):
            for generic in (False, True):
                response = self.transition(working, fields, generic)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn(b'private database', response.content)
                self.assertEqual(response.json()['code'], 'internal_error')
                self.assertEqual(self.snapshot(), before)
        done = self.data(self.transition(working, fields))
        self.assertEqual(self.data(self.transition(working, fields, True), True), done)
        self.assertEqual((AuditEvent.objects.count(), Outbox.objects.count(), IdempotencyResult.objects.count()), (1, 1, 1))
        self.assertEqual(IssueTransition.objects.filter(to_key='hold').count(), 1)
