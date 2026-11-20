from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import connections
from django.test import TransactionTestCase
from tests.support import WorkpalCase
from tests.test_issue_state_review import StateFixtures
from workpal.access.service import derive_scope
from workpal.actions.registry import execute
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.identity.models import Membership
from workpal.work import issues, transitions, dependencies, service as projects
from workpal.work.models import Issue, IssueDependency


class DependencyReview(StateFixtures, WorkpalCase):
    def link(self, row, target, key='link', remove=False):
        return self.act(self.actor, 'issue.dependency.' + ('remove' if remove else 'add'),
                        {'issue_id': row['id'], 'depends_on_id': target['id']},
                        key=key, revision=row['revision']).data

    def test_unfinished_cancelled_and_archived_dependencies_block_manual_completion(self):
        row = self.move(self.issue, 'working')
        target = issues.create(self.actor, self.project['id'], 'Prerequisite')
        row = self.link(row, target)
        def denied():
            before = self.tables()
            with self.assertRaises(DomainError) as caught:
                self.move(row, 'finished', key='finish', reason='Ready')
            self.assertEqual(caught.exception.code, 'dependency_blocked')
            self.assertEqual(self.tables(), before)
            self.assertTrue(dependencies.unresolved_dependencies(self.actor, row['id']))
        denied()
        target = self.move(target, 'working')
        target = self.move(target, 'stopped')
        self.assertEqual(target['lifecycle'], 'closed')
        denied()
        target = issues.archive(self.actor, target['id'], target['revision'])
        denied()
        target = issues.restore(self.actor, target['id'], target['revision'])
        target = self.move(target, 'incoming')
        target = self.move(target, 'working')
        target = self.move(target, 'finished', reason='Verified prerequisite')
        self.assertFalse(dependencies.unresolved_dependencies(self.actor, row['id']))
        self.assertEqual(issues.read(self.actor, row['id'])['status_key'], 'working')
        self.assertEqual(self.move(row, 'finished', key='finish', reason='Ready')['status_category'], 'done')

    def test_same_workspace_cross_project_link_is_allowed_but_foreign_or_self_is_not(self):
        other_project = projects.create(self.actor, 'Other project')
        target = issues.create(self.actor, other_project['id'], 'Same workspace')
        row = self.link(self.issue, target)
        self.assertEqual(row['revision'], 2)
        self.assertEqual(issues.read(self.actor, target['id'])['revision'], 1)
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        other_actor = Actor(self.user.pk, self.other.pk)
        foreign_project = projects.create(other_actor, 'Foreign')
        foreign = issues.create(other_actor, foreign_project['id'], 'Foreign')
        before = self.tables()
        for invalid in (row, foreign):
            with self.subTest(target=invalid['id']), self.assertRaises(DomainError):
                self.link(row, invalid, key='invalid')
        self.assertEqual(self.tables(), before)

    def test_reactivation_is_unique_and_removal_retains_restricted_provenance(self):
        target = issues.create(self.actor, self.project['id'], 'Restricted')
        grant = self.grant(self.a, read=True, write=True)
        self.register(self.workspace.pk, issues.ref(target['id']), [self.a])
        row = self.link(self.issue, target)
        before = self.tables()
        self.assertEqual(self.link(self.issue, target), row)
        with self.assertRaises(DomainError) as caught:
            self.link(row, target, key='duplicate')
        self.assertEqual(caught.exception.code, 'dependency_exists')
        self.assertEqual(self.tables(), before)
        row = self.link(row, target, key='remove', remove=True)
        self.assertEqual(IssueDependency.objects.count(), 1)
        self.assertFalse(IssueDependency.objects.get().active)
        row = self.link(row, target, key='reactivate')
        self.assertEqual(IssueDependency.objects.count(), 1)
        self.assertTrue(IssueDependency.objects.get().active)
        self.link(row, target, key='remove-again', remove=True)
        self.assertEqual(derive_scope([issues.ref(row['id'])]).source_refs, {self.a})
        grant.read = False
        grant.save()
        with self.assertRaises(DomainError):
            issues.read(self.actor, row['id'])

    def test_revocation_denies_history_dependency_queries_and_previous_action_results(self):
        row = self.move(self.issue, 'working', key='move')
        target = issues.create(self.actor, self.project['id'], 'Restricted prerequisite')
        grant = self.grant(self.a, read=True, write=True)
        self.register(self.workspace.pk, issues.ref(target['id']), [self.a])
        self.link(row, target)
        grant.read = False
        grant.save()
        operations = [
            lambda: transitions.list_transitions(self.actor, row['id']),
            lambda: dependencies.list_dependencies(self.actor, row['id']),
            lambda: dependencies.unresolved_dependencies(self.actor, row['id']),
            lambda: self.move(self.issue, 'working', key='move'),
            lambda: self.link(row, target),
        ]
        for operation in operations:
            with self.assertRaises(DomainError) as caught:
                operation()
            self.assertEqual(caught.exception.status, 403)

    def test_dependency_pages_and_issue_filters_use_only_visible_matches(self):
        targets = [issues.create(self.actor, self.project['id'], str(i)) for i in range(3)]
        row = self.issue
        for target in targets:
            row = self.link(row, target, key=str(target['id']))
        seen, cursor = [], 0
        while True:
            page = self.act(self.actor, 'issue.dependency.list',
                             {'issue_id': row['id'], 'cursor': cursor, 'limit': 1}).data
            self.assertEqual(set(page), {'items', 'next_cursor'})
            seen.extend(item['depends_on_id'] for item in page['items'])
            cursor = page['next_cursor']
            if not cursor:
                break
        self.assertEqual(seen, [target['id'] for target in targets])
        visible = self.move(targets[0], 'working')
        assigned = issues.update(self.actor, targets[1]['id'], 1, assignee_user_id=self.user.pk)
        assigned = self.move(assigned, 'working')
        hidden = self.move(targets[2], 'working')
        self.register(self.workspace.pk, issues.ref(hidden['id']), [self.a])
        page = self.act(self.actor, 'issue.list', {'status_key': 'working', 'assignee_user_id': 0, 'limit': 1}).data
        self.assertEqual([item['id'] for item in page['items']], [visible['id']])
        self.assertEqual(page['next_cursor'], 0)
        page = self.act(self.actor, 'issue.list', {'status_key': 'working', 'assignee_user_id': self.user.pk}).data
        self.assertEqual([item['id'] for item in page['items']], [assigned['id']])

    def test_late_add_and_remove_failure_roll_back_edges_provenance_and_results(self):
        target = issues.create(self.actor, self.project['id'], 'Prerequisite')
        before = self.tables()
        with patch.object(issues, 'view', side_effect=RuntimeError('late projection failure')):
            with self.assertRaises(RuntimeError):
                self.link(self.issue, target)
        self.assertEqual(self.tables(), before)
        row = self.link(self.issue, target)
        before = self.tables()
        with patch.object(issues, 'view', side_effect=RuntimeError('late projection failure')):
            with self.assertRaises(RuntimeError):
                self.link(row, target, key='remove', remove=True)
        self.assertEqual(self.tables(), before)
        removed = self.link(row, target, key='remove', remove=True)
        self.assertEqual(removed['revision'], 3)
        self.assertFalse(IssueDependency.objects.get().active)
        self.assertCountEqual(list(Outbox.objects.values_list('action_id', flat=True)),
                              ['issue.dependency.add', 'issue.dependency.remove'])


class ConcurrentDependencyReview(StateFixtures, TransactionTestCase):
    def race(self, reverse):
        a = self.issue
        b = issues.create(self.actor, self.project['id'], 'Other')
        barrier = Barrier(2)
        pairs = [(a, b, 'forward'), (b, a, 'reverse')] if reverse else [(a, b, 'same')] * 2
        def run(item):
            connections.close_all()
            try:
                connection = connections['default']
                connection.ensure_connection()
                identity = id(connection.connection)
                source, target, key = item
                barrier.wait(timeout=10)
                try:
                    result = execute(self.actor, ActionRequest('issue.dependency.add',
                        {'issue_id': source['id'], 'depends_on_id': target['id']}, 1, key))
                    return identity, result.state, result.data
                except DomainError as error:
                    return identity, error.code, error.status
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, pairs))
        self.assertEqual(len({result[0] for result in results}), 2)
        self.assertEqual(IssueDependency.objects.filter(active=True).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action_id='issue.dependency.add').count(), 1)
        self.assertEqual(Outbox.objects.count(), 1)
        self.assertCountEqual(list(Issue.objects.values_list('revision', flat=True)), [1, 2])
        for row in (a, b):
            derive_scope([issues.ref(row['id'])])
        return results

    def test_concurrent_opposite_edges_cannot_form_cycle(self):
        results = self.race(True)
        self.assertCountEqual([result[1] for result in results], ['completed', 'dependency_cycle'])

    def test_concurrent_same_key_adds_one_edge_and_replays_result(self):
        results = self.race(False)
        self.assertEqual(results[0][1:], results[1][1:])
        self.assertEqual(results[0][1], 'completed')
