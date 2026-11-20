import hashlib
import json
from unittest.mock import patch

from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.actions.models import Confirmation, IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError
from workpal.identity.models import Membership
from workpal.work import service
from workpal.work.models import Project
from workpal.workflows import service as workflows
from workpal.workflows.models import WorkflowDraft, WorkflowVersion


class ProjectWorkflowReview(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()
        self.project = service.create(self.actor, 'Project')
        draft = workflows.create(self.actor, 'Flow')
        self.version = workflows.publish(self.actor, draft['id'], 1)
        self.payload = {'project_id': self.project['id'], 'workflow_version_id': self.version['id']}

    def prepare(self):
        result = self.act(self.actor, 'project.set_workflow', self.payload, key='bind', revision=1)
        self.assertEqual(result.state, 'waiting_confirmation')
        return result.data['confirmation_id']

    def consume(self, token):
        return self.act(self.actor, 'project.set_workflow', self.payload, key='bind',
                        revision=1, confirmation_id=token)

    def assert_unmodified(self, token=None, revision=1):
        project = Project.objects.get(pk=self.project['id'])
        self.assertIsNone(project.workflow_version_id)
        self.assertEqual(project.revision, revision)
        self.assertFalse(IdempotencyResult.objects.filter(action_id='project.set_workflow').exists())
        self.assertFalse(AuditEvent.objects.filter(action_id='project.set_workflow').exists())
        self.assertFalse(Outbox.objects.filter(action_id='project.set_workflow').exists())
        if token:
            self.assertFalse(Confirmation.objects.get(pk=token).consumed)

    def test_foreign_workspace_version_cannot_be_bound_even_by_common_owner(self):
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        other_actor = Actor(self.user.pk, self.other.pk)
        draft = workflows.create(other_actor, 'Private other workspace')
        version = workflows.publish(other_actor, draft['id'], 1)
        self.assertEqual(workflows.read_version(other_actor, version['id'])['name'], draft['name'])
        self.payload['workflow_version_id'] = version['id']
        with self.assertRaises(DomainError) as caught:
            self.prepare()
        self.assertEqual(caught.exception.status, 404)
        self.assertFalse(Confirmation.objects.exists())
        self.assert_unmodified()
        with self.assertRaises(DomainError) as caught:
            service.snapshot_workflow(other_actor, self.project['id'])
        self.assertEqual(caught.exception.status, 404)

    def test_unpublished_draft_is_not_a_published_version(self):
        draft = workflows.create(self.actor, 'Unpublished')
        self.assertFalse(WorkflowVersion.objects.filter(pk=draft['id']).exists())
        self.payload['workflow_version_id'] = draft['id']
        with self.assertRaises(DomainError) as caught:
            self.prepare()
        self.assertEqual(caught.exception.status, 404)
        for payload in ({'project_id': self.project['id'], 'draft_id': draft['id']},
                        {**self.payload, 'draft_id': draft['id']}):
            with self.assertRaises(DomainError) as caught:
                self.act(self.actor, 'project.set_workflow', payload, key='bad', revision=1)
            self.assertEqual(caught.exception.status, 400)
        self.assert_unmodified()

    def test_source_revocation_while_waiting_denies_and_does_not_consume(self):
        self.register(self.workspace.pk, workflows.ref(self.version['id'], True), [self.a])
        grant = self.grant(self.a, read=True, write=True)
        token = self.prepare()
        for field in ('write', 'read'):
            setattr(grant, field, False)
            grant.save()
            with self.assertRaises(DomainError) as caught:
                self.consume(token)
            self.assertEqual(caught.exception.status, 403)
            self.assert_unmodified(token)
            setattr(grant, field, True)
            grant.save()
        result = self.consume(token)
        self.assertEqual(result.data['workflow_version_id'], self.version['id'])
        self.assertTrue(Confirmation.objects.get(pk=token).consumed)
        self.assertEqual(Outbox.objects.filter(action_id='project.set_workflow').count(), 1)

    def test_source_scope_change_requires_new_confirmation(self):
        token = self.prepare()
        self.register(self.workspace.pk, workflows.ref(self.version['id'], True), [self.a])
        self.grant(self.a, read=True, write=True)
        with self.assertRaises(DomainError) as caught:
            self.consume(token)
        self.assertEqual(caught.exception.code, 'confirmation_conflict')
        self.assert_unmodified(token)
        fresh = self.act(self.actor, 'project.set_workflow', self.payload, key='fresh', revision=1)
        result = self.act(self.actor, 'project.set_workflow', self.payload, key='fresh', revision=1,
                          confirmation_id=fresh.data['confirmation_id'])
        self.assertEqual(result.data['workflow_version_id'], self.version['id'])

    def test_revision_change_during_confirmation_preserves_concurrent_edit(self):
        token = self.prepare()
        service.update(self.actor, self.project['id'], 1, name='Concurrent rename')
        with self.assertRaises(DomainError) as caught:
            self.consume(token)
        self.assertEqual(caught.exception.code, 'revision_conflict')
        self.assert_unmodified(token, revision=2)
        self.assertEqual(service.read(self.actor, self.project['id'])['name'], 'Concurrent rename')

    def test_late_registration_failure_rolls_back_binding_and_confirmation(self):
        token = self.prepare()
        with patch.object(service, 'register_object', side_effect=RuntimeError('late failure')):
            with self.assertRaises(RuntimeError):
                self.consume(token)
        self.assert_unmodified(token)
        completed = self.consume(token)
        self.assertEqual(completed.data['revision'], 2)
        self.assertEqual(Outbox.objects.filter(action_id='project.set_workflow').count(), 1)

    def test_builtin_hash_covers_the_returned_content_without_creating_versions(self):
        before = (WorkflowDraft.objects.count(), WorkflowVersion.objects.count())
        snapshot = service.snapshot_workflow(self.actor, self.project['id'])
        content = {key: snapshot[key] for key in ('name', 'definition')}
        digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':'),
                                           ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        self.assertEqual(snapshot['sha256'], digest)
        self.assertEqual(snapshot['origin'], 'builtin')
        self.assertEqual(snapshot['version_id'], 0)
        self.assertEqual((WorkflowDraft.objects.count(), WorkflowVersion.objects.count()), before)
