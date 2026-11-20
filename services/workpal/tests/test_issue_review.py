from copy import deepcopy
import hashlib
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model

from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.access.models import RegisteredObject, SourceGrant, SourceLink
from workpal.access.service import derive_scope
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError, ObjectRef
from workpal.identity.models import Membership
from workpal.work import issues, service as projects
from workpal.work.models import Issue, IssueRequirements
from workpal.workflows import service as workflows


class IssueReview(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()
        self.project = projects.create(self.actor, 'Same name')

    def create(self, key='create', **changes):
        return self.act(self.actor, 'issue.create',
                        {'project_id': self.project['id'], 'title': 'Task', **changes}, key=key).data

    def tables(self):
        models = (Issue, IssueRequirements, RegisteredObject, SourceLink,
                  IdempotencyResult, AuditEvent, Outbox)
        return {model.__name__: list(model.objects.order_by('pk').values()) for model in models}

    def test_published_workflow_is_pinned_after_project_rebinding_and_reset(self):
        definition = {
            'states': [{'key': 'incoming', 'label': 'Incoming', 'category': 'backlog'},
                       {'key': 'finished', 'label': 'Finished', 'category': 'done'}],
            'transitions': [{'from': 'incoming', 'to': 'finished'}],
            'review_policy': {'completion': 'manual', 'reviewer_roles': ['member']},
        }
        draft = workflows.create(self.actor, 'Custom flow', definition)
        first = workflows.publish(self.actor, draft['id'], 1)
        project = projects.set_workflow(self.actor, self.project['id'], first['id'], 1)
        issue = self.create()
        expected = deepcopy(issue['workflow_snapshot'])
        self.assertEqual(issue['status_key'], 'incoming')
        self.assertEqual(expected['version_id'], first['id'])
        self.assertEqual(expected['definition'], definition)
        changed = deepcopy(definition)
        changed['review_policy']['completion'] = 'approved_delivery'
        draft = workflows.update(self.actor, draft['id'], 2, name='New flow', definition=changed)
        second = workflows.publish(self.actor, draft['id'], draft['revision'])
        project = projects.set_workflow(self.actor, project['id'], second['id'], project['revision'])
        self.assertEqual(self.create(key='second')['workflow_snapshot']['version_id'], second['id'])
        projects.set_workflow(self.actor, project['id'], 0, project['revision'])
        self.assertEqual(self.create(key='builtin')['workflow_snapshot']['origin'], 'builtin')
        self.assertEqual(issues.read(self.actor, issue['id'])['workflow_snapshot'], expected)
        issue['workflow_snapshot']['definition']['states'].clear()
        self.assertEqual(issues.read(self.actor, issue['id'])['workflow_snapshot'], expected)

    def test_assignee_requires_current_same_workspace_membership_and_read_grants(self):
        person = get_user_model().objects.create(username='assignee')
        Membership.objects.create(user=person, workspace=self.other, role='owner')
        before = self.tables()
        with self.assertRaises(DomainError):
            self.create(assignee_user_id=person.pk)
        self.assertEqual(self.tables(), before)
        link = Membership.objects.create(user=person, workspace=self.workspace, role='member')
        self.grant(self.a, read=True, write=True)
        source = {'kind': self.a.kind, 'id': self.a.id}
        before = self.tables()
        with self.assertRaises(DomainError):
            self.create(assignee_user_id=person.pk, source_refs=[source])
        self.assertEqual(self.tables(), before)
        grant = SourceGrant.objects.create(user=person,
            source=RegisteredObject.objects.get(kind=self.a.kind, object_id=self.a.id), read=True)
        row = self.create(assignee_user_id=person.pk, source_refs=[source])
        self.assertEqual(issues.read(Actor(person.pk, self.workspace.pk), row['id'])['id'], row['id'])
        grant.read = False
        grant.save()
        before = self.tables()
        with self.assertRaises(DomainError):
            self.act(self.actor, 'issue.update', {'issue_id': row['id'], 'assignee_user_id': person.pk}, key='bad', revision=1)
        self.assertEqual(self.tables(), before)
        link.delete()
        with self.assertRaises(DomainError):
            self.act(self.actor, 'issue.update', {'issue_id': row['id'], 'assignee_user_id': person.pk}, key='bad', revision=1)
        cleared = self.act(self.actor, 'issue.update', {'issue_id': row['id'], 'assignee_user_id': 0}, key='clear', revision=1).data
        self.assertEqual(cleared['assignee_user_id'], 0)
        self.assertEqual(cleared['requirements_version_id'], row['requirements_version_id'])

    def test_archived_project_blocks_new_issues_but_preserves_existing_work(self):
        row = self.create()
        projects.update(self.actor, self.project['id'], 1, archived=True)
        before = self.tables()
        with self.assertRaises(DomainError) as caught:
            self.create(key='new', title='Cannot create')
        self.assertEqual(caught.exception.code, 'project_archived')
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.tables(), before)
        edited = self.act(self.actor, 'issue.update', {'issue_id': row['id'], 'title': 'Still editable'}, key='edit', revision=1).data
        archived = self.act(self.actor, 'issue.archive', {'issue_id': row['id']}, key='archive', revision=2).data
        self.assertEqual(issues.list_issues(self.actor)['items'], [])
        self.assertEqual(issues.list_issues(self.actor, include_archived=True)['items'][0]['id'], row['id'])
        restored = self.act(self.actor, 'issue.restore', {'issue_id': row['id']}, key='restore', revision=3).data
        self.assertFalse(restored['archived'])
        self.assertEqual(archived['status_key'], restored['status_key'])
        self.assertEqual(restored['requirements_version_id'], edited['requirements_version_id'])
        self.assertEqual(issues.read_requirements(self.actor, row['id'], 1)['title'], 'Task')

    def test_create_retry_and_assignment_produce_only_one_business_event_each(self):
        other = projects.create(self.actor, 'Same name')
        row = self.create(project_id=other['id'])
        again = self.create(project_id=other['id'])
        self.assertEqual(row, again)
        self.assertEqual(row['project_id'], other['id'])
        self.assertEqual(Issue.objects.count(), 1)
        self.assertEqual(IssueRequirements.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action_id='issue.create').count(), 1)
        self.assertEqual(Outbox.objects.filter(action_id='issue.create').count(), 1)
        with self.assertRaises(DomainError) as caught:
            self.create(title='Changed request', project_id=other['id'])
        self.assertEqual(caught.exception.code, 'idempotency_conflict')
        assigned = self.act(self.actor, 'issue.update', {'issue_id': row['id'], 'assignee_user_id': self.user.pk}, key='assign', revision=1).data
        self.assertEqual(assigned['requirements_version_id'], row['requirements_version_id'])
        self.assertEqual(assigned['status_key'], 'backlog')
        self.assertCountEqual(list(Outbox.objects.values_list('action_id', flat=True)),
                              ['issue.create', 'issue.update'])
        count = Outbox.objects.count()
        self.act(self.actor, 'issue.read', {'issue_id': row['id']})
        self.act(self.actor, 'issue.requirements.read', {'issue_id': row['id'], 'number': 1})
        self.assertEqual(Outbox.objects.count(), count)

    def test_cross_workspace_objects_and_inactive_assignee_leave_no_rows(self):
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        foreign = Actor(self.user.pk, self.other.pk)
        other_project = projects.create(foreign, 'Foreign project')
        other_source = self.register(self.other.pk, ObjectRef('doc', 'foreign'))
        inactive = get_user_model().objects.create(username='inactive', is_active=False)
        Membership.objects.create(user=inactive, workspace=self.workspace, role='member')
        for changes in ({'project_id': other_project['id']},
                        {'source_refs': [{'kind': other_source.kind, 'id': other_source.id}]},
                        {'assignee_user_id': inactive.pk}):
            with self.subTest(changes=changes):
                before = self.tables()
                with self.assertRaises(DomainError):
                    self.create(**changes)
                self.assertEqual(self.tables(), before)
        row = self.create()
        for action, payload in (('issue.read', {'issue_id': row['id']}),
                                ('issue.requirements.read', {'issue_id': row['id'], 'number': 1})):
            with self.assertRaises(DomainError) as caught:
                self.act(foreign, action, payload)
            self.assertEqual(caught.exception.status, 404)
        self.assertEqual(issues.list_issues(foreign), {'items': [], 'next_cursor': 0})

    def test_requirements_hash_and_history_include_exact_criteria_values(self):
        row = self.create(description='范围', criteria=[{'key': 'retry_safe', 'text': '不会重复上传'}])
        old = issues.read_requirements(self.actor, row['id'], 1)
        content = {key: old[key] for key in ('title', 'description', 'criteria')}
        digest = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                           separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        self.assertEqual(old['sha256'], digest)
        edited = self.act(self.actor, 'issue.update', {'issue_id': row['id'], 'criteria': [
            {'key': 'retry_safe', 'text': 'All retries remain unique'}]}, key='edit', revision=1).data
        self.assertEqual(edited['requirements_revision'], 2)
        self.assertEqual(issues.read_requirements(self.actor, row['id'], 1), old)
        edited['criteria'][0]['text'] = 'Client mutation'
        self.assertEqual(issues.read(self.actor, row['id'])['criteria'][0]['text'], 'All retries remain unique')

    def test_multi_source_restrictions_survive_empty_sources_and_filter_before_pagination(self):
        self.grant(self.a, read=True, write=True)
        b = self.grant(self.b, read=True, write=True)
        row = self.create(title='Hidden secret', source_refs=[{'kind': self.a.kind, 'id': self.a.id}])
        self.act(self.actor, 'issue.update', {'issue_id': row['id'], 'source_refs': [
            {'kind': self.b.kind, 'id': self.b.id}]}, key='source', revision=1)
        self.act(self.actor, 'issue.update', {'issue_id': row['id'], 'source_refs': []}, key='empty', revision=2)
        self.assertEqual(derive_scope([issues.ref(row['id'])]).source_refs, {self.a, self.b})
        first = self.create(key='visible1', title='Visible first')
        last = self.create(key='visible2', title='Visible last')
        b.read = False
        b.save()
        for action, payload, kwargs in (
            ('issue.read', {'issue_id': row['id']}, {}),
            ('issue.requirements.read', {'issue_id': row['id'], 'number': 1}, {}),
            ('issue.update', {'issue_id': row['id'], 'source_refs': []}, {'key': 'empty', 'revision': 2}),
        ):
            with self.assertRaises(DomainError):
                self.act(self.actor, action, payload, **kwargs)
        page = self.act(self.actor, 'issue.list', {'project_id': self.project['id'], 'limit': 1}).data
        self.assertEqual([item['id'] for item in page['items']], [first['id']])
        self.assertEqual(page['next_cursor'], first['id'])
        page = self.act(self.actor, 'issue.list', {'cursor': page['next_cursor'], 'limit': 1}).data
        self.assertEqual([item['id'] for item in page['items']], [last['id']])
        self.assertEqual(page['next_cursor'], 0)
        self.assertEqual(self.act(self.actor, 'issue.list', {'query': 'secret'}).data,
                         {'items': [], 'next_cursor': 0})

    def test_late_create_and_update_failure_roll_back_all_owned_tables(self):
        original = issues.register_object
        def fail_after_registration(workspace, ref, sources=()):
            result = original(workspace, ref, sources)
            if ref.kind == 'issue_requirements':
                raise RuntimeError('late registration failure')
            return result
        before = self.tables()
        with patch.object(issues, 'register_object', fail_after_registration):
            with self.assertRaises(RuntimeError):
                self.create()
        self.assertEqual(self.tables(), before)
        row = self.create()
        self.grant(self.a, read=True, write=True)
        before = self.tables()
        payload = {'issue_id': row['id'], 'title': 'New title',
                   'source_refs': [{'kind': self.a.kind, 'id': self.a.id}]}
        with patch.object(issues, 'register_object', fail_after_registration):
            with self.assertRaises(RuntimeError):
                self.act(self.actor, 'issue.update', payload, key='edit', revision=1)
        self.assertEqual(self.tables(), before)
        edited = self.act(self.actor, 'issue.update', payload, key='edit', revision=1).data
        self.assertEqual(edited['requirements_revision'], 2)
        self.assertEqual(Outbox.objects.filter(action_id='issue.update').count(), 1)

    def test_invalid_criteria_and_readonly_payloads_are_rejected_without_writes(self):
        bad_criteria = [[{'key': 'bad', 'text': '  '}],
                        [{'key': 'bad', 'text': 'ok'}, {'key': 'bad', 'text': 'duplicate'}],
                        [{'key': 'Uppercase', 'text': 'ok'}],
                        [{'key': 'valid', 'text': 'ok', 'extra': True}]]
        for criteria in bad_criteria:
            with self.subTest(criteria=criteria), self.assertRaises(DomainError):
                self.create(criteria=criteria)
        self.assertFalse(Issue.objects.exists())
        row = self.create()
        before = self.tables()
        for fields in ({'title': ' \t '}, {'status_key': 'done'}, {'workflow_snapshot': {}},
                       {'workspace_id': self.other.pk}, {'assignee_user_id': True}):
            with self.subTest(fields=fields), self.assertRaises(DomainError) as caught:
                self.act(self.actor, 'issue.update', {'issue_id': row['id'], **fields}, key='bad', revision=1)
            self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.tables(), before)

    def test_direct_service_rejects_unencodable_text_as_domain_input_error(self):
        for fields in ({'title': '\ud800'}, {'description': '\ud800'},
                       {'criteria': [{'key': 'test', 'text': '\ud800'}]}):
            with self.subTest(fields=fields):
                with self.assertRaises(DomainError) as caught:
                    issues.create(self.actor, self.project['id'], **{'title': 'Task', **fields})
                self.assertEqual(caught.exception.status, 400)
        self.assertFalse(Issue.objects.exists())
