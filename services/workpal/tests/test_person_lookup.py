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
from workpal.identity.directory import read_person
from workpal.identity.models import Membership, Workspace
from workpal.storage import MAX_SQLITE_INTEGER
from .support import WorkpalCase


class PersonLookupTests(WorkpalCase):
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


    def test_registry_reads_exact_person(self):
        target = self.person('target')
        result = self.act(self.actor, 'workspace.people.read', {'user_id': target.pk})
        self.assertEqual(result.state, 'completed')
        self.assertEqual(result.data, {'person': {'user_id': target.pk, 'username': target.username}})

    def http_session(self):
        client = Client(enforce_csrf_checks=True)
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        response = client.post('/api/v1/auth/login', json.dumps({
            'username': self.user.username, 'password': 'directory-password'}),
            content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        return client, client.get('/api/v1/auth/csrf').json()['csrf_token']


    def test_http_auth_csrf_host_and_revoked_session_cannot_expose_directory(self):
        client, token = self.http_session()
        url = '/api/v1/actions/workspace.people.read'
        body = json.dumps({'workspace_id': self.workspace.pk, 'payload': {'user_id': self.user.pk}})
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
        self.assertFalse(AuditEvent.objects.filter(action_id='workspace.people.read').exists())
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
            self.assertEqual(self.directory(target.pk).data, {'person': {'user_id': target.pk, 'username': target.username}})
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

    def directory(self, user_id):
        return self.act(self.actor, 'workspace.people.read', {'user_id': user_id})

    def test_roles_tail_and_live_visibility(self):
        for i in range(21):
            target = self.person(f'tail-{i}')
        for role in ('owner', 'admin', 'member'):
            Membership.objects.filter(user=self.user, workspace=self.workspace).update(role=role)
            self.assertEqual(self.directory(target.pk).data,
                             {'person': {'user_id': target.pk, 'username': target.username}})
        Membership.objects.create(user=target, workspace=self.other, role='member')
        Membership.objects.filter(user=target, workspace=self.workspace).delete()
        self.assertEqual(self.directory(target.pk).data, {})
        self.assertEqual(self.directory(MAX_SQLITE_INTEGER).data, {})
        Membership.objects.create(user=target, workspace=self.workspace, role='member')
        target.is_active = False
        target.save()
        self.assertEqual(self.directory(target.pk).data, {})
        for inactive in (False, True):
            if inactive:
                Membership.objects.create(user=self.user, workspace=self.workspace, role='member')
                self.user.is_active = False
                self.user.save()
            else:
                Membership.objects.filter(user=self.user).delete()
            with self.assertRaises(DomainError) as caught:
                self.directory(target.pk)
            self.assertEqual(caught.exception.status, 404)

    def test_strict_inputs(self):
        for value in (None, True, False, '1', 1.0, 0, -1, MAX_SQLITE_INTEGER + 1, [], {}):
            for call in (lambda: read_person(self.actor, value), lambda: self.directory(value)):
                with self.subTest(value=repr(value)), self.assertRaises(DomainError) as caught:
                    call()
                self.assertEqual(caught.exception.status, 400)
        for field in ('workspace_id', 'role', 'username'):
            with self.assertRaises(DomainError) as caught:
                self.act(self.actor, 'workspace.people.read', {'user_id': self.user.pk, field: 1})
            self.assertEqual(caught.exception.status, 400)

    def test_projection_and_read_only_audit(self):
        target = self.person('secret-name')
        before = self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            result = read_person(self.actor, target.pk)
        self.assertEqual(self.snapshot(), before)
        selects = [q['sql'].split(' FROM ', 1)[0] for q in queries if q['sql'].startswith('SELECT')]
        self.assertTrue(any('"auth_user"."username"' in sql for sql in selects))
        for sql in selects:
            for field in ('email', 'password', 'is_active', 'is_staff', 'is_superuser', 'last_login'):
                self.assertNotIn(f'"auth_user"."{field}"', sql)
        for user_id, expected in ((target.pk, result), (MAX_SQLITE_INTEGER, {})):
            before = self.snapshot(exclude=(AuditEvent,))
            prior_ids = list(AuditEvent.objects.values_list('pk', flat=True))
            count = len(prior_ids)
            response = self.directory(user_id)
            self.assertEqual(response.data, expected)
            self.assertEqual(response.object_refs, [])
            self.assertEqual(self.snapshot(exclude=(AuditEvent,)), before)
            self.assertEqual(AuditEvent.objects.count(), count + 1)
            event = AuditEvent.objects.exclude(pk__in=prior_ids).get()
            self.assertEqual(event.fields, {'user_id': user_id})
            self.assertEqual(event.action_id, 'workspace.people.read')
            self.assertEqual(event.outcome, 'completed')
            self.assertEqual(event.scope_refs, [])
            self.assertEqual(event.object_refs, [])

    def test_http_success_empty_and_management(self):
        client, token = self.http_session()
        for user_id, expected in ((self.user.pk, {'person': {'user_id': self.user.pk, 'username': self.user.username}}),
                                  (MAX_SQLITE_INTEGER, {})):
            body = {'workspace_id': self.workspace.pk, 'payload': {'user_id': user_id}}
            response = client.post('/api/v1/actions/workspace.people.read', json.dumps(body),
                                   content_type='application/json', HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['data'], expected)
            self.assertIn('no-store', response.headers['Cache-Control'])
        body = {'workspace_id': self.workspace.pk, 'payload': {}}
        self.assertEqual(client.post('/api/v1/actions/member.list', json.dumps(body),
                         content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 403)
        body = {'workspace_id': self.other.pk, 'payload': {'user_id': self.user.pk}}
        self.assertEqual(client.post('/api/v1/actions/workspace.people.read', json.dumps(body),
                         content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 404)
