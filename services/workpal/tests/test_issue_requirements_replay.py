"""Exact-version replay and direct-write rollback regression coverage."""
from copy import deepcopy
from django.contrib.auth import get_user_model
from workpal.contracts import Actor, DomainError, ObjectRef
from workpal.identity.models import Membership, Workspace
from workpal.access.service import register_object
from workpal.actions.models import IdempotencyResult
from workpal.work import issues
from workpal.work.models import Issue
from .support import WorkpalCase


class RequirementsReplayTests(WorkpalCase):
    def setUp(self):
        user = get_user_model().objects.create_user('replay-reader')
        workspace = Workspace.objects.create(name='Replay')
        Membership.objects.create(user=user, workspace=workspace, role='owner')
        self.actor = Actor(user.pk, workspace.pk)
        project = self.act(self.actor, 'project.create', {'name': 'P'}, key='p').data
        self.payload = {'project_id': project['id'], 'title': 'Old'}
        self.old = self.act(self.actor, 'issue.create', self.payload, key='i').data
        self.source = register_object(workspace.pk, ObjectRef('source', 'private-replay'), is_source=True)

    def deny(self, operation):
        with self.assertRaises(DomainError) as caught:
            operation()
        self.assertEqual(caught.exception.status, 403)

    def test_legacy_cache_uses_old_version_after_current_changes(self):
        self.act(self.actor, 'issue.update', {'issue_id': self.old['id'], 'title': 'New'}, revision=1, key='u')
        saved = IdempotencyResult.objects.get(action_id='issue.create', key='i')
        original = deepcopy(saved.result)
        saved.result['object_refs'] = [r for r in saved.result['object_refs'] if r['kind'] != 'issue_requirements']
        saved.scope_refs = [r for r in saved.scope_refs if r['kind'] != 'issue_requirements']
        saved.save()
        register_object(self.actor.workspace_id, issues.requirement_ref(self.old['requirements_version_id']), [self.source])
        self.deny(lambda: self.act(self.actor, 'issue.create', self.payload, key='i'))
        self.assertEqual(issues.read(self.actor, self.old['id'])['title'], 'New')
        saved.refresh_from_db()
        self.assertEqual(saved.result['data'], original['data'])

    def test_missing_cached_version_fails_closed(self):
        saved = IdempotencyResult.objects.get(action_id='issue.create', key='i')
        del saved.result['data']['requirements_version_id']
        saved.save()
        self.deny(lambda: self.act(self.actor, 'issue.create', self.payload, key='i'))

    def test_archive_output_denial_rolls_back(self):
        register_object(self.actor.workspace_id, issues.requirement_ref(self.old['requirements_version_id']), [self.source])
        self.deny(lambda: issues.archive(self.actor, self.old['id'], 1))
        row = Issue.objects.get(pk=self.old['id'])
        self.assertFalse(row.archived)
        self.assertEqual(row.revision, 1)

    def test_partial_update_cannot_copy_private_content(self):
        register_object(self.actor.workspace_id, issues.requirement_ref(self.old['requirements_version_id']), [self.source])
        self.deny(lambda: issues.update(self.actor, self.old['id'], 1, description='copy'))
        row = Issue.objects.get(pk=self.old['id'])
        self.assertEqual(row.revision, 1)
        self.assertEqual(row.current_requirements_id, self.old['requirements_version_id'])
