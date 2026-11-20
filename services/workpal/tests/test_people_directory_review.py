"""Directory acceptance through its public read and action Interfaces."""
import json
from dataclasses import replace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from workpal.actions.registry import catalog
from workpal.audit.models import AuditEvent
from workpal.contracts import Actor, DomainError, ObjectRef
from workpal.identity.directory import list_people
from workpal.identity.models import Membership, Workspace
from workpal.storage import MAX_SQLITE_INTEGER
from .support import WorkpalCase


class DirectoryReviewTests(WorkpalCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(name='Directory')
        self.other = Workspace.objects.create(name='Other')
        self.user = get_user_model().objects.create_user('member', password='directory-password')
        Membership.objects.create(user=self.user, workspace=self.workspace, role='member')
        self.actor = Actor(self.user.pk, self.workspace.pk)

    def person(self, name, workspace=None, active=True):
        user = get_user_model().objects.create(
            username=name, email='private@example.invalid', password='private-hash', is_active=active)
        Membership.objects.create(user=user, workspace=workspace or self.workspace, role='member')
        return user

    def snapshot(self, exclude=()):
        return {model._meta.label: list(model.objects.order_by('pk').values())
                for model in apps.get_models() if model not in exclude}

    def directory(self, payload=None, actor=None):
        return self.act(actor or self.actor, 'workspace.people.list', payload or {})

    def test_filtering_precedes_three_pages_and_cursor_is_user_identity(self):
        expected = []
        for index in range(7):
            self.person(f'Pick-hidden-{index}', self.other)
            self.person(f'Pick-disabled-{index}', active=False)
            expected.append(self.person(f'Pick-visible-{index}').pk)
        shared = self.person('Pick-shared', self.other)
        Membership.objects.create(user=shared, workspace=self.workspace, role='admin')
        expected.append(shared.pk)
        cursor = 0
        found = []
        for count in (3, 3, 2):
            page = self.directory({'query': 'pick', 'cursor': cursor, 'limit': 3}).data
            self.assertEqual(len(page['items']), count)
            found.extend(item['user_id'] for item in page['items'])
            cursor = page['next_cursor']
            self.assertEqual(cursor, found[-1] if len(found) < len(expected) else 0)
        self.assertEqual(found, expected)
        self.assertEqual(self.directory({'query': 'shared', 'cursor': 0}).data['items'],
                         [{'user_id': shared.pk, 'username': shared.username}])
        self.assertEqual(list_people(self.actor, cursor=MAX_SQLITE_INTEGER)['items'], [])

    def test_special_search_characters_are_literal_and_whitespace_is_preserved(self):
        names = ['Alpha%_match', 'AlphaXXmatch', ' spaced ', 'spaced']
        users = [self.person(name) for name in names]
        for query, expected in [('aLPHA%_', users[:1]), ('%', users[:1]), ('_', users[:1]),
                                (' spaced ', users[2:3]), ('absent', [])]:
            self.assertEqual(self.directory({'query': query}).data['items'],
                             [{'user_id': user.pk, 'username': user.username} for user in expected])

    def test_target_revocation_is_live_and_cannot_use_another_workspace_membership(self):
        target = self.person('target')
        Membership.objects.create(user=target, workspace=self.other, role='member')
        Membership.objects.create(user=self.user, workspace=self.other, role='member')
        self.assertIn(target.pk, [item['user_id'] for item in self.directory().data['items']])
        Membership.objects.filter(user=target, workspace=self.workspace).delete()
        self.assertNotIn(target.pk, [item['user_id'] for item in self.directory().data['items']])
        other_actor = replace(self.actor, workspace_id=self.other.pk)
        self.assertIn(target.pk, [item['user_id'] for item in self.directory(actor=other_actor).data['items']])
        target.is_active = False
        target.save(update_fields=['is_active'])
        self.assertNotIn(target.pk, [item['user_id'] for item in self.directory(actor=other_actor).data['items']])
        Membership.objects.filter(user=self.user, workspace=self.workspace).delete()
        with self.assertRaises(DomainError) as caught:
            self.directory()
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.directory(actor=other_actor).state, 'completed')
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        with self.assertRaises(DomainError) as caught:
            self.directory(actor=other_actor)
        self.assertEqual(caught.exception.status, 404)

    def test_registry_rejects_null_types_unknown_fields_and_invalid_unicode(self):
        before = self.snapshot()
        invalid = []
        for field, values in {
            'query': [None, True, 1, [], {}, 'x' * 151, '\x00', '\ud800'],
            'cursor': [None, True, -1, MAX_SQLITE_INTEGER + 1, 1.0, '1'],
            'limit': [None, True, 0, 201, 1.0, '1'],
        }.items():
            invalid.extend({field: value} for value in values)
        invalid.extend([{field: 1} for field in ('workspace_id', 'user_id', 'role', 'is_active')])
        for payload in invalid:
            with self.subTest(payload=repr(payload)), self.assertRaises(DomainError) as caught:
                self.directory(payload)
            self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.snapshot(), before)

    def test_direct_projection_and_registry_audit_are_minimal_and_read_only(self):
        target = self.person('audit-search-name')
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            direct = list_people(self.actor, query='audit-', cursor=0, limit=20)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(direct, {'items': [{'user_id': target.pk, 'username': target.username}], 'next_cursor': 0})
        selects = [query['sql'].split(' FROM ', 1)[0] for query in queries if query['sql'].startswith('SELECT')]
        self.assertTrue(any('"auth_user"."username"' in sql for sql in selects))
        for sql in selects:
            for field in ('password', 'email', 'is_staff', 'is_superuser', 'is_active', 'last_login'):
                self.assertNotIn(f'"auth_user"."{field}"', sql)
        before = self.snapshot(exclude=(AuditEvent,))
        result = self.directory({'query': 'audit-', 'cursor': 0, 'limit': 20})
        self.assertEqual(result.data, direct)
        self.assertEqual(result.object_refs, [])
        self.assertEqual(self.snapshot(exclude=(AuditEvent,)), before)
        event = AuditEvent.objects.get()
        self.assertEqual((event.actor_id, event.workspace_id, event.action_id, event.outcome),
                         (self.user.pk, self.workspace.pk, 'workspace.people.list', 'completed'))
        self.assertEqual(event.fields, {'cursor': 0, 'limit': 20})
        self.assertEqual(event.scope_refs, [])
        self.assertEqual(event.object_refs, [])
        serialized = json.dumps(list(AuditEvent.objects.values()), default=str)
        for value in ('audit-search-name', 'private@example.invalid', 'private-hash'):
            self.assertNotIn(value, serialized)
        definition = next(item for item in catalog(self.actor) if item['action_id'] == 'workspace.people.list')
        for flag in ('mutating', 'confirmation_required', 'revision_required', 'idempotency_required'):
            self.assertFalse(definition[flag])

    def http_session(self):
        client = Client(enforce_csrf_checks=True)
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        response = client.post('/api/v1/auth/login', json.dumps({
            'username': self.user.username, 'password': 'directory-password'}),
            content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        return client, client.get('/api/v1/auth/csrf').json()['csrf_token']

    def test_real_login_http_matches_registry_and_keeps_management_restricted(self):
        target = self.person('same-workspace')
        foreign = self.person('other-workspace', self.other)
        client, token = self.http_session()
        url = '/api/v1/actions/workspace.people.list'
        body = {'workspace_id': self.workspace.pk, 'payload': {}}
        response = client.post(url, json.dumps(body), content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(response.json()['data'], self.directory().data)
        self.assertIn(target.pk, [item['user_id'] for item in response.json()['data']['items']])
        self.assertNotIn(foreign.pk, [item['user_id'] for item in response.json()['data']['items']])
        response = client.post('/api/v1/actions/member.list', json.dumps(body), content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 403)
        body['workspace_id'] = self.other.pk
        response = client.post(url, json.dumps(body), content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 404)

    def test_http_auth_csrf_host_and_revoked_session_cannot_expose_directory(self):
        client, token = self.http_session()
        url = '/api/v1/actions/workspace.people.list'
        body = json.dumps({'workspace_id': self.workspace.pk, 'payload': {}})
        for response, status in (
            (client.post(url, body, content_type='application/json'), 403),
            (client.post(url, body, content_type='application/json', HTTP_X_CSRFTOKEN=token,
                         HTTP_HOST='evil.invalid'), 400),
            (client.get('/api/v1/actions', {'workspace_id': self.workspace.pk}), 200),
            (client.get(f'/api/v1/workspaces/{self.workspace.pk}'), 200),
            (client.get('/api/v1/no-such-endpoint'), 404),
        ):
            self.assertEqual(response.status_code, status)
            self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        Membership.objects.filter(user=self.user, workspace=self.workspace).delete()
        self.assertEqual(client.post(url, body, content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 404)
        self.assertFalse(AuditEvent.objects.filter(action_id='workspace.people.list').exists())
        client.logout()
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.assertEqual(client.post(url, body, content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 403)

    def test_visible_person_does_not_gain_issue_or_requirement_permission(self):
        from workpal.access.models import RegisteredObject, SourceGrant
        from workpal.access.service import register_object
        from workpal.work import issues
        Membership.objects.filter(user=self.user, workspace=self.workspace).update(role='owner')
        target = self.person('potential-assignee')
        project = self.act(self.actor, 'project.create', {'name': 'Project'}, key='project').data
        source = register_object(self.workspace.pk, ObjectRef('source', 'directory-review'), is_source=True)
        source_row = RegisteredObject.objects.get(kind=source.kind, object_id=source.id)
        SourceGrant.objects.create(user=self.user, source=source_row, read=True, write=True)
        for requirement_only in (False, True):
            item = issues.create(self.actor, project['id'], 'Restricted issue')
            ref = issues.requirement_ref(item['requirements_version_id']) if requirement_only else issues.ref(item['id'])
            register_object(self.workspace.pk, ref, [source])
            self.assertIn(target.pk, [row['user_id'] for row in self.directory().data['items']])
            before = self.snapshot()
            with self.assertRaises(DomainError) as caught:
                self.act(self.actor, 'issue.update', {'issue_id': item['id'], 'assignee_user_id': target.pk},
                         revision=item['revision'], key=f'assign-{requirement_only}')
            self.assertEqual(caught.exception.status, 403)
            self.assertEqual(self.snapshot(), before)
        SourceGrant.objects.create(user=target, source=source_row, read=True)
        updated = self.act(self.actor, 'issue.update', {'issue_id': item['id'], 'assignee_user_id': target.pk},
                           revision=item['revision'], key='assign-after-grant')
        self.assertEqual(updated.data['assignee_user_id'], target.pk)
