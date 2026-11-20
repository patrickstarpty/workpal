from unittest.mock import patch

from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.contracts import DomainError
from workpal.work import service
from workpal.work.models import Project


class ProjectReviewTests(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()

    def test_public_service_cannot_move_project_across_workspaces(self):
        project = self.act(self.actor, 'project.create', {'name': 'Original'}, key='p').data
        with self.assertRaises(DomainError):
            service.update(self.actor, project['id'], 1, workspace_id=self.other.pk)
        row = Project.objects.get(pk=project['id'])
        self.assertEqual((row.workspace_id, row.revision), (self.workspace.pk, 1))

    def test_public_create_rolls_back_if_registration_fails(self):
        # Fault only the second local step; the real SQLite transaction must
        # undo the preceding row insert, even for direct service consumers.
        with patch.object(service, 'register_object', side_effect=RuntimeError('registration failed')):
            with self.assertRaises(RuntimeError):
                service.create(self.actor, 'must roll back')
        self.assertFalse(Project.objects.filter(name='must roll back').exists())

    def test_project_name_cannot_be_only_whitespace(self):
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, 'project.create', {'name': ' \t '}, key='blank')
        self.assertEqual(caught.exception.status, 400)
        self.assertFalse(Project.objects.exists())

    def test_omitted_description_is_preserved_but_explicit_empty_clears(self):
        project = self.act(self.actor, 'project.create',
                           {'name': 'Original', 'description': 'Keep this context'}, key='p').data
        renamed = self.act(self.actor, 'project.update',
                           {'project_id': project['id'], 'name': 'Renamed'}, key='rename', revision=1).data
        self.assertEqual(renamed['description'], 'Keep this context')
        cleared = self.act(self.actor, 'project.update',
                           {'project_id': project['id'], 'name': 'Renamed', 'description': ''},
                           key='clear', revision=2).data
        self.assertEqual(cleared['description'], '')
