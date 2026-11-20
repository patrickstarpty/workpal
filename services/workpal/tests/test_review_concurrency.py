from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase
from tests.support import WorkpalCase
from tests.test_review_validation import ReviewFixtures
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.delivery.models import DeliveryCurrent, DeliverySelection, Review
from workpal.identity.models import Membership
from workpal.work.models import Issue


class ReviewConcurrency(ReviewFixtures, TransactionTestCase):
    act = WorkpalCase.act

    def peer(self):
        user = get_user_model().objects.create(username='second-reviewer')
        Membership.objects.create(user=user, workspace=self.workspace, role='admin')
        for source in (self.a, self.b):
            SourceGrant.objects.create(user=user, source=RegisteredObject.objects.get(kind=source.kind,
                object_id=source.id), read=True, write=True)
        return Actor(user.pk, self.workspace.pk)

    def race(self, mode):
        target = self.ready()
        peer = self.peer()
        candidate = self.submit('candidate') if mode == 'switch' else None
        requests = [(self.actor, ActionRequest('delivery.review', dict(delivery_id=target['id'],
            version=target['number'], decision=dict(outcome='approve', reason='Human decision.')), 2, 'first'))]
        if mode == 'same':
            requests.append(requests[0])
        elif mode == 'reviewers':
            requests.append((peer, ActionRequest('delivery.review', dict(delivery_id=target['id'],
                version=target['number'], decision=dict(outcome='request_changes', reason='Please revise.')), 2, 'second')))
        else:
            requests.append((peer, ActionRequest('delivery.select_current', dict(delivery_id=candidate['id'],
                reason='Use the candidate.'), 2, 'second')))
        actions = ('delivery.review', 'delivery.select_current')
        counts = {model: model.objects.filter(action_id__in=actions).count()
                  for model in (AuditEvent, Outbox, IdempotencyResult)}
        issues_before = list(Issue.objects.values())
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
                except DomainError as exc:
                    return identity, exc.status, exc.code, actor.user_id
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, requests))
        self.assertNotEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(result[1] for result in results), [200, 200] if mode == 'same' else [200, 409])
        self.assertEqual(DeliveryCurrent.objects.get().revision, 3)
        self.assertEqual(list(Issue.objects.values()), issues_before)
        for model, count in counts.items():
            self.assertEqual(model.objects.filter(action_id__in=actions).count(), count + 1)
        if mode != 'switch':
            self.assertEqual((Review.objects.count(), DeliverySelection.objects.count()), (1, 1))
            winner = next(result for result in results if result[1] == 200)
            self.assertEqual(Review.objects.get().actor_id, winner[3])
        else:
            self.assertEqual(Review.objects.count() + DeliverySelection.objects.count(), 2)
            if Review.objects.exists():
                self.assertEqual(DeliveryCurrent.objects.get().current_delivery_id, target['id'])
            else:
                self.assertEqual(DeliveryCurrent.objects.get().current_delivery_id, candidate['id'])
        if mode == 'same':
            self.assertEqual(results[0][2], results[1][2])

    def test_same_key_commits_one_review_across_two_connections(self):
        self.race('same')

    def test_two_human_reviewers_cannot_commit_two_decisions_for_one_revision(self):
        self.race('reviewers')

    def test_review_and_current_switch_share_the_same_revision_gate(self):
        self.race('switch')
