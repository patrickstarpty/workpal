from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase
from tests.support import WorkpalCase
from tests.test_completion_review import CompletionFixtures
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import ActionRequest, Actor, DomainError, SubjectRef
from workpal.delivery import approval
from workpal.delivery.models import DeliveryCurrent
from workpal.identity.models import Membership
from workpal.work.models import Issue, IssueTransition


class CompletionConcurrency(CompletionFixtures, TransactionTestCase):
    act = WorkpalCase.act

    def peer(self):
        user = get_user_model().objects.create(username='completion-peer')
        Membership.objects.create(user=user, workspace=self.workspace, role='owner')
        for source in (self.a, self.b):
            SourceGrant.objects.create(user=user, source=RegisteredObject.objects.get(
                kind=source.kind, object_id=source.id), read=True, write=True)
        return Actor(user.pk, self.workspace.pk)

    def race(self, mode):
        target, saved = self.approved()
        peer = self.peer()
        finish = dict(issue_id=self.issue['id'], target='finished', reason='Accepted')
        requests = [(self.actor, ActionRequest('issue.transition', finish, 1, 'finish'))]
        if mode == 'same':
            requests.append(requests[0])
        elif mode == 'different':
            requests.append((peer, ActionRequest('issue.transition', finish, 1, 'peer-finish')))
        elif mode == 'requirements':
            requests.append((peer, ActionRequest('issue.update',
                dict(issue_id=self.issue['id'], title='New requirements'), 1, 'requirements')))
        elif mode == 'review':
            requests.append((peer, ActionRequest('delivery.review', dict(delivery_id=target['id'],
                version=target['number'], decision=dict(outcome='request_changes', reason='Revise this.')),
                3, 'new-review')))
        else:
            candidate = self.submit('candidate')
            requests.append((peer, ActionRequest('delivery.select_current',
                dict(delivery_id=candidate['id'], reason='Select candidate'), 3, 'new-choice')))
        actions = {request.action_id for _, request in requests}
        counts = {model: model.objects.filter(action_id__in=actions).count()
                  for model in (AuditEvent, Outbox, IdempotencyResult)}
        barrier = Barrier(2)
        def run(item):
            actor, request = item
            connections.close_all()
            try:
                connection = connections['default']
                connection.ensure_connection()
                identity = id(connection.connection)
                barrier.wait(timeout=10)
                try:
                    result = registry.execute(actor, request)
                    return identity, 200, result.data, actor.user_id
                except DomainError as error:
                    return identity, error.status, error.code, actor.user_id
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, requests))
        self.assertNotEqual(results[0][0], results[1][0])
        if mode in ('same', 'different', 'requirements'):
            self.assertEqual(sorted(item[1] for item in results), [200, 200] if mode == 'same' else [200, 409])
        else:
            self.assertEqual(results[1][1], 200)
            self.assertIn(results[0][1], (200, 409))
            if results[0][1] == 409:
                self.assertEqual(results[0][2], 'completion_not_ready')
        successful_writes = 1 if mode == 'same' else sum(item[1] == 200 for item in results)
        for model, count in counts.items():
            self.assertEqual(model.objects.filter(action_id__in=actions).count(), count + successful_writes)
        completed = any(result[1] == 200 and request.action_id == 'issue.transition'
                        for result, (_, request) in zip(results, requests))
        history = IssueTransition.objects.filter(issue_id=self.issue['id'])
        self.assertEqual(history.count(), int(completed))
        issue = Issue.objects.select_related('current_requirements').get(pk=self.issue['id'])
        self.assertEqual(issue.status_key, 'finished' if completed else 'start')
        self.assertEqual(issue.revision, 2 if completed or mode == 'requirements' else 1)
        if completed:
            event = history.get()
            self.assertEqual(event.completion_review_id, saved['id'])
            self.assertEqual(event.completion_snapshot['review_revision'], 3)
            self.assertEqual(event.completion_snapshot['current_delivery_id'], target['id'])
            self.assertEqual(event.requirements_version_id, self.issue['requirements_version_id'])
        if mode == 'same':
            self.assertEqual(results[0][2], results[1][2])
        if mode == 'requirements':
            self.assertEqual(issue.current_requirements.number, 1 if completed else 2)
        if mode in ('review', 'selection'):
            self.assertEqual(DeliveryCurrent.objects.get(subject_id=self.subject['id']).revision, 4)
            self.assertEqual(approval.inspect(self.actor, SubjectRef(**self.subject))[0]['status'], 'not_approved')

    def test_same_key_on_two_connections_completes_once(self):
        self.race('same')

    def test_two_humans_competing_for_one_issue_revision_complete_once(self):
        self.race('different')

    def test_new_requirements_and_completion_share_the_issue_revision(self):
        self.race('requirements')

    def test_new_review_and_completion_follow_transaction_order(self):
        self.race('review')

    def test_new_selection_and_completion_follow_transaction_order(self):
        self.race('selection')
