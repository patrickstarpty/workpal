from django.contrib.auth import get_user_model

from workpal.contracts import Actor, DomainError, ObjectRef
from workpal.identity.models import Membership, Workspace
from workpal.access.models import SourceGrant, RegisteredObject
from workpal.access.service import register_object
from workpal.work import issues
from workpal.audit.models import AuditEvent
from .support import WorkpalCase


class IssueRequirementsAccessTests(WorkpalCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('requirements-reader')
        self.workspace = Workspace.objects.create(name='Workspace')
        Membership.objects.create(user=self.user, workspace=self.workspace, role='owner')
        self.actor = Actor(self.user.pk, self.workspace.pk)
        self.project = self.act(self.actor, 'project.create', {'name': 'Project'}, key='project').data
        self.payload = {'project_id': self.project['id'], 'title': 'Private current content',
                        'description': 'Private description', 'criteria': [{'key': 'private', 'text': 'Private criterion'}]}
        self.issue = self.act(self.actor, 'issue.create', self.payload, key='issue').data
        self.source = register_object(self.workspace.pk, ObjectRef('source', 'requirements-source'), is_source=True)

    def restrict(self, version_id):
        register_object(self.workspace.pk, issues.requirement_ref(version_id), [self.source])

    def deny(self, operation):
        with self.assertRaises(DomainError) as caught:
            operation()
        self.assertEqual(caught.exception.status, 403)

    def test_current_requirement_restriction_applies_to_issue_read(self):
        self.restrict(self.issue['requirements_version_id'])
        self.deny(lambda: issues.read(self.actor, self.issue['id']))
        self.deny(lambda: self.act(self.actor, 'issue.read', {'issue_id': self.issue['id']}))

    def test_current_requirement_restriction_filters_issue_list_before_pagination(self):
        self.restrict(self.issue['requirements_version_id'])
        visible = self.act(self.actor, 'issue.create', {'project_id': self.project['id'], 'title': 'Visible'}, key='visible').data
        for page in (issues.list_issues(self.actor, limit=1), self.act(self.actor, 'issue.list', {'limit': 1}).data):
            self.assertEqual([item['id'] for item in page['items']], [visible['id']])
            self.assertEqual(page['next_cursor'], 0)

    def test_current_requirement_restriction_blocks_cached_create_content(self):
        self.restrict(self.issue['requirements_version_id'])
        self.deny(lambda: self.act(self.actor, 'issue.create', self.payload, key='issue'))

    def test_history_is_independent_and_read_audit_tracks_the_exact_version(self):
        current = self.act(self.actor, 'issue.update', {'issue_id': self.issue['id'], 'title': 'New public version'}, key='update', revision=1).data
        self.restrict(self.issue['requirements_version_id'])
        self.assertEqual(self.act(self.actor, 'issue.read', {'issue_id': current['id']}).data['title'], 'New public version')
        self.deny(lambda: self.act(self.actor, 'issue.requirements.read', {'issue_id': current['id'], 'number': 1}))
        source = RegisteredObject.objects.get(kind=self.source.kind, object_id=self.source.id)
        SourceGrant.objects.create(user=self.user, source=source, read=True)
        result = self.act(self.actor, 'issue.requirements.read', {'issue_id': current['id'], 'number': 1})
        required = issues.requirement_ref(self.issue['requirements_version_id'])
        self.assertIn(required, result.object_refs)
        event = AuditEvent.objects.filter(action_id='issue.requirements.read').latest('created_at')
        self.assertIn({'kind': required.kind, 'id': required.id}, event.scope_refs)
