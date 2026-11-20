"""Independent checks for live directory facts and the read action contract."""
import json
from dataclasses import replace

from django.contrib.auth import get_user_model
from django.test import Client

from workpal.actions.registry import catalog
from workpal.audit.models import AuditEvent
from workpal.contracts import Actor, DomainError
from workpal.identity.directory import read_person
from workpal.identity.models import Membership, Workspace
from .support import WorkpalCase


class PersonLookupReviewTests(WorkpalCase):
    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user('requester', password='lookup-password')
        self.target = users.objects.create_user('target')
        self.first = Workspace.objects.create(name='First')
        self.second = Workspace.objects.create(name='Second')
        for workspace in (self.first, self.second):
            Membership.objects.create(user=self.user, workspace=workspace, role='member')
        Membership.objects.create(user=self.target, workspace=self.first, role='member')
        self.actor = Actor(self.user.pk, self.first.pk)

    def test_revoked_requester_cannot_read_an_active_target_directly_or_via_registry(self):
        expected = {'person': {'user_id': self.target.pk, 'username': self.target.username}}
        self.assertEqual(read_person(self.actor, self.target.pk), expected)
        Membership.objects.filter(user=self.user, workspace=self.first).delete()
        for inactive in (False, True):
            if inactive:
                Membership.objects.create(user=self.user, workspace=self.first, role='member')
                self.user.is_active = False
                self.user.save(update_fields=['is_active'])
            for actor in (self.actor, replace(self.actor, executor_id='lookup-agent')):
                for call in (lambda: read_person(actor, self.target.pk),
                             lambda: self.act(actor, 'workspace.people.read', {'user_id': self.target.pk})):
                    with self.subTest(inactive=inactive, executor=actor.executor_id), self.assertRaises(DomainError) as caught:
                        call()
                    self.assertEqual(caught.exception.status, 404)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)
        self.assertTrue(Membership.objects.filter(user=self.target, workspace=self.first).exists())
        self.assertFalse(AuditEvent.objects.filter(action_id='workspace.people.read').exists())

    def test_http_reads_current_username_and_visibility_in_each_authorized_workspace(self):
        client = Client(enforce_csrf_checks=True)
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        response = client.post('/api/v1/auth/login', json.dumps({
            'username': 'requester', 'password': 'lookup-password'}),
            content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']

        def read(workspace, expected):
            response = client.post('/api/v1/actions/workspace.people.read', json.dumps({
                'workspace_id': workspace.pk, 'payload': {'user_id': self.target.pk}}),
                content_type='application/json', HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['data'], expected)
            self.assertIn('no-store', response.headers['Cache-Control'])

        original = {'person': {'user_id': self.target.pk, 'username': 'target'}}
        read(self.first, original)
        read(self.second, {})
        Membership.objects.create(user=self.target, workspace=self.second, role='member')
        self.target.username = 'Renamed <person>'
        self.target.save(update_fields=['username'])
        renamed = {'person': {'user_id': self.target.pk, 'username': self.target.username}}
        read(self.first, renamed)
        read(self.second, renamed)
        Membership.objects.filter(user=self.target, workspace=self.first).delete()
        read(self.first, {})
        read(self.second, renamed)
        self.target.is_active = False
        self.target.save(update_fields=['is_active'])
        read(self.second, {})
        events = AuditEvent.objects.filter(action_id='workspace.people.read')
        self.assertEqual(events.count(), 7)
        for event in events:
            self.assertEqual(event.fields, {'user_id': self.target.pk})
        serialized = json.dumps(list(events.values()), default=str)
        self.assertNotIn('Renamed <person>', serialized)

    def test_catalog_is_read_only_and_missing_or_extra_arguments_have_no_audit(self):
        definition = next(item for item in catalog(self.actor)
                          if item['action_id'] == 'workspace.people.read')
        for flag in ('mutating', 'confirmation_required', 'revision_required', 'idempotency_required'):
            self.assertFalse(definition[flag])
        for payload in ({}, {'user_id': self.target.pk, 'actor': self.actor.user_id},
                        {'user_id': self.target.pk, 'executor_id': 'lookup-agent'},
                        {'user_id': self.target.pk, 'query': 'target'}):
            with self.subTest(payload=payload), self.assertRaises(DomainError) as caught:
                self.act(self.actor, 'workspace.people.read', payload)
            self.assertEqual(caught.exception.status, 400)
        self.assertFalse(AuditEvent.objects.filter(action_id='workspace.people.read').exists())
