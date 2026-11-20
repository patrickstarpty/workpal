from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase
from tests.support import WorkpalCase
from tests.test_issue_state_review import StateFixtures
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.access.service import derive_scope
from workpal.actions.registry import execute
from workpal.audit.models import AuditEvent, Outbox
from workpal.collaboration import service as collaboration
from workpal.collaboration.models import Notification
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.identity.models import Membership
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work import hierarchy, issues, service as projects
from workpal.work.models import Issue


class HierarchyFixtures(StateFixtures):
    def setUp(self):
        super().setUp()
        self.parent = issues.create(self.actor, self.project['id'], 'Parent')
        self.target = get_user_model().objects.create(username='child-reader')
        Membership.objects.create(user=self.target, workspace=self.workspace, role='member')
        self.recipient = Actor(self.target.pk, self.workspace.pk)

    def snapshot(self):
        return {m._meta.label: list(m.objects.order_by('pk').values()) for m in apps.get_models()}

    def attach(self, row, parent_id, key='attach', actor=None):
        return self.act(actor or self.actor, 'issue.set_parent',
                        {'issue_id': row['id'], 'parent_issue_id': parent_id},
                        key=key, revision=row['revision']).data

    def restrict(self, row, source):
        self.register(self.workspace.pk, issues.ref(row['id']), [source])

    def recipient_grant(self, source):
        return SourceGrant.objects.create(user=self.target,
            source=RegisteredObject.objects.get(kind=source.kind, object_id=source.id), read=True)


class HierarchyReview(HierarchyFixtures, WorkpalCase):
    def test_reparent_and_detach_keep_all_historical_sources_and_replay_checks(self):
        grant_a = self.grant(self.a, read=True, write=True)
        self.grant(self.b, read=True, write=True)
        self.restrict(self.parent, self.a)
        other = issues.create(self.actor, self.project['id'], 'Other parent')
        self.restrict(other, self.b)
        attached = self.attach(self.issue, self.parent['id'])
        moved = self.attach(attached, other['id'], 'reparent')
        detached = self.attach(moved, 0, 'detach')
        self.assertEqual(detached['parent_issue_id'], 0)
        self.assertEqual(derive_scope([issues.ref(self.issue['id'])]).source_refs, {self.a, self.b})
        self.assertEqual(issues.read(self.actor, self.parent['id']), self.parent)
        self.assertEqual(issues.read(self.actor, other['id']), other)
        grant_a.read = False
        grant_a.save()
        with self.assertRaises(DomainError) as caught:
            self.attach(moved, 0, 'detach')
        self.assertEqual(caught.exception.status, 403)
        with self.assertRaises(DomainError) as caught:
            issues.read(self.actor, detached['id'])
        self.assertEqual(caught.exception.status, 403)

    def test_children_authorize_before_paging_without_restricting_parent(self):
        self.grant(self.a, read=True, write=True)
        hidden = issues.create(self.actor, self.project['id'], 'Secret child', parent_issue_id=self.parent['id'])
        self.restrict(hidden, self.a)
        visible = [issues.create(self.actor, self.project['id'], title, parent_issue_id=self.parent['id'])
                   for title in ('First', 'Second')]
        first = self.act(self.recipient, 'issue.children.list', {'issue_id': self.parent['id'], 'limit': 1})
        self.assertEqual([i['id'] for i in first.data['items']], [visible[0]['id']])
        self.assertEqual(first.data['next_cursor'], visible[0]['id'])
        self.assertEqual(set(first.object_refs), {issues.ref(self.parent['id']), issues.ref(visible[0]['id']), issues.requirement_ref(visible[0]['requirements_version_id'])})
        second = self.act(self.recipient, 'issue.children.list',
                          {'issue_id': self.parent['id'], 'limit': 1, 'cursor': first.data['next_cursor']}).data
        self.assertEqual([i['id'] for i in second['items']], [visible[1]['id']])
        self.assertEqual(second['next_cursor'], 0)
        self.assertEqual(set(second), {'items', 'next_cursor'})
        issues.archive(self.actor, visible[0]['id'], 1)
        filtered = self.act(self.recipient, 'issue.list', {'parent_issue_id': self.parent['id'],
                            'project_id': self.project['id'], 'query': 'Second',
                            'status_key': 'incoming', 'assignee_user_id': 0}).data
        self.assertEqual([i['id'] for i in filtered['items']], [visible[1]['id']])
        all_visible = hierarchy.children(self.recipient, self.parent['id'], include_archived=True)
        self.assertEqual([i['id'] for i in all_visible['items']], [i['id'] for i in visible])
        self.assertEqual(issues.read(self.recipient, self.parent['id']), self.parent)
        self.restrict(self.parent, self.a)
        with self.assertRaises(DomainError) as caught:
            self.act(self.recipient, 'issue.list', {'parent_issue_id': self.parent['id'], 'query': 'missing'})
        self.assertEqual(caught.exception.status, 403)

    def test_assignee_guard_and_existing_comment_notifications_inherit_parent(self):
        assigned = issues.update(self.actor, self.issue['id'], 1, assignee_user_id=self.target.pk)
        comment = collaboration.create(self.actor, assigned['id'], 'Mention', mention_user_ids=[self.target.pk])
        notices = list(Notification.objects.order_by('pk').values())
        self.grant(self.a, read=True, write=True)
        self.restrict(self.parent, self.a)
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.attach(assigned, self.parent['id'])
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
        reader_grant = self.recipient_grant(self.a)
        attached = self.attach(assigned, self.parent['id'])
        self.assertEqual(attached['assignee_user_id'], self.target.pk)
        self.assertEqual(list(Notification.objects.order_by('pk').values()), notices)
        self.assertEqual(collaboration.read(self.recipient, comment['id'])['id'], comment['id'])
        self.assertEqual(len(collaboration.listing(self.recipient)['items']), 2)
        reader_grant.read = False
        reader_grant.save()
        self.assertEqual(collaboration.listing(self.recipient), {'items': [], 'next_cursor': 0})
        with self.assertRaises(DomainError) as caught:
            collaboration.read(self.recipient, comment['id'])
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(list(Notification.objects.order_by('pk').values()), notices)

    def test_child_creation_recipient_failure_rolls_back_then_same_key_retries(self):
        self.grant(self.a, read=True, write=True)
        self.restrict(self.parent, self.a)
        payload = {'project_id': self.project['id'], 'parent_issue_id': self.parent['id'],
                   'title': 'Assigned child', 'assignee_user_id': self.target.pk}
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, 'issue.create', payload, key='child-create')
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
        self.recipient_grant(self.a)
        result = self.act(self.actor, 'issue.create', payload, key='child-create')
        self.assertEqual(result.data['parent_issue_id'], self.parent['id'])
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(self.act(self.actor, 'issue.create', payload, key='child-create').data, result.data)
        self.assertEqual(Outbox.objects.filter(action_id='issue.create').count(), 1)

    def test_detached_historical_source_cycle_is_rejected_without_erasing_sources(self):
        attached = self.attach(self.issue, self.parent['id'])
        self.attach(attached, 0, 'detach')
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.attach(self.parent, self.issue['id'], 'historical-cycle')
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)

    def test_late_source_failure_rolls_back_all_tables_and_same_key_retries(self):
        original = hierarchy.register_object
        def fail_after_source(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('unavailable', 'Try again.', status=503)
        before = self.snapshot()
        with patch.object(hierarchy, 'register_object', fail_after_source):
            with self.assertRaises(DomainError) as caught:
                self.attach(self.issue, self.parent['id'])
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        attached = self.attach(self.issue, self.parent['id'])
        self.assertEqual(attached['revision'], 2)
        self.assertEqual(self.attach(self.issue, self.parent['id']), attached)
        self.assertEqual(Outbox.objects.filter(action_id='issue.set_parent').count(), 1)

    def test_archived_parent_blocks_new_attachment_but_keeps_existing_replay(self):
        payload = {'project_id': self.project['id'], 'parent_issue_id': self.parent['id'], 'title': 'Child'}
        created = self.act(self.actor, 'issue.create', payload, key='child-create').data
        attached = self.attach(self.issue, self.parent['id'])
        issues.archive(self.actor, self.parent['id'], 1)
        self.assertEqual(self.attach(self.issue, self.parent['id']), attached)
        self.assertEqual(self.act(self.actor, 'issue.create', payload, key='child-create').data, created)
        before = self.snapshot()
        for action in (lambda: self.act(self.actor, 'issue.create', payload, key='new-create'),
                       lambda: self.attach(attached, self.parent['id'], 'new-attach')):
            with self.assertRaises(DomainError) as caught:
                action()
            self.assertEqual(caught.exception.code, 'issue_archived')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(issues.read(self.actor, created['id'])['archived'], False)
        self.assertEqual(self.attach(attached, 0, 'detach')['parent_issue_id'], 0)

    def test_cross_workspace_parent_is_not_found_and_preserves_all_tables(self):
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        other_actor = Actor(self.user.pk, self.other.pk)
        other_project = projects.create(other_actor, 'Other')
        foreign = issues.create(other_actor, other_project['id'], 'Foreign')
        before = self.snapshot()
        for action in (lambda: self.attach(self.issue, foreign['id']),
                       lambda: issues.create(self.actor, self.project['id'], 'Child', parent_issue_id=foreign['id'])):
            with self.assertRaises(DomainError) as caught:
                action()
            self.assertEqual((caught.exception.status, caught.exception.code), (404, 'not_found'))
        self.assertEqual(self.snapshot(), before)

    def test_cross_project_child_owns_its_snapshot_and_lifecycle(self):
        builtin = projects.create(self.actor, 'Builtin')
        child = issues.create(self.actor, builtin['id'], 'Own workflow', parent_issue_id=self.parent['id'])
        self.assertEqual(child['status_key'], 'backlog')
        self.assertEqual(child['workflow_snapshot']['origin'], 'builtin')
        self.assertNotEqual(child['workflow_snapshot'], self.parent['workflow_snapshot'])
        projects.set_workflow(self.actor, builtin['id'], self.project['workflow_version_id'], 1)
        detached = self.attach(child, 0)
        self.assertEqual(detached['workflow_snapshot'], child['workflow_snapshot'])
        own = issues.create(self.actor, self.project['id'], 'Independent', parent_issue_id=self.parent['id'])
        working = self.move(own, 'working')
        done = self.move(working, 'finished', reason='Human verified')
        self.assertEqual(done['status_category'], 'done')
        issues.archive(self.actor, own['id'], done['revision'])
        self.assertEqual(issues.read(self.actor, self.parent['id']), self.parent)

    def test_plain_member_can_attach_only_with_current_write_on_both_issues(self):
        self.grant(self.a, read=True, write=True)
        parent_grant = self.grant(self.b, read=True, write=False)
        self.restrict(self.issue, self.a)
        self.restrict(self.parent, self.b)
        self.member.role = 'member'
        self.member.save()
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.attach(self.issue, self.parent['id'])
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
        parent_grant.write = True
        parent_grant.save()
        self.assertEqual(self.attach(self.issue, self.parent['id'])['parent_issue_id'], self.parent['id'])

    def test_direct_and_registry_parent_fields_reject_invalid_integer_types(self):
        before = self.snapshot()
        for value in (True, '1', -1, None, MAX_SQLITE_INTEGER):
            for field in ('issue_id', 'parent_issue_id', 'revision'):
                args = dict(issue_id=self.issue['id'], parent_issue_id=self.parent['id'], revision=1)
                args[field] = value
                with self.subTest(value=value, field=field):
                    with self.assertRaises(DomainError) as caught:
                        hierarchy.set_parent(self.actor, **args)
                    self.assertEqual(caught.exception.status, 400)
            with self.subTest(value=value, interface='registry'):
                with self.assertRaises(DomainError) as caught:
                    self.act(self.actor, 'issue.set_parent', {'issue_id': self.issue['id'], 'parent_issue_id': value},
                             key='invalid', revision=1)
                self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.snapshot(), before)


class ConcurrentHierarchy(HierarchyFixtures, TransactionTestCase):
    act = WorkpalCase.act

    def race(self, same_key):
        barrier = Barrier(2)
        def invoke(index):
            connections.close_all()
            try:
                connection = connections['default']
                connection.ensure_connection()
                identity = id(connection.connection)
                child, parent = ((self.issue, self.parent) if same_key or index == 0 else (self.parent, self.issue))
                barrier.wait(timeout=10)
                try:
                    result = execute(self.actor, ActionRequest('issue.set_parent',
                        {'issue_id': child['id'], 'parent_issue_id': parent['id']}, 1, 'same' if same_key else str(index)))
                    return identity, result.data
                except DomainError as error:
                    return identity, error
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(invoke, range(2)))
        self.assertNotEqual(results[0][0], results[1][0])
        self.assertEqual(Outbox.objects.filter(action_id='issue.set_parent').count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action_id='issue.set_parent').count(), 1)
        return [r[1] for r in results]

    def test_same_key_two_connections_produces_one_revision_and_one_event(self):
        results = self.race(True)
        self.assertEqual(results[0], results[1])
        self.assertEqual(issues.read(self.actor, self.issue['id'])['revision'], 2)
        self.assertEqual(issues.read(self.actor, self.parent['id'])['revision'], 1)

    def test_reverse_parent_two_connections_cannot_commit_a_cycle(self):
        results = self.race(False)
        errors = [r for r in results if isinstance(r, DomainError)]
        self.assertEqual(len(errors), 1)
        self.assertEqual((errors[0].status, errors[0].code), (409, 'hierarchy_cycle'))
        self.assertEqual(Issue.objects.exclude(parent=None).count(), 1)
        self.assertEqual(sorted(Issue.objects.values_list('revision', flat=True)), [1, 2])
