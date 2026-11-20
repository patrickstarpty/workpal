from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import connections
from django.test import TransactionTestCase
from tests.support import WorkpalCase
from tests.test_delivery import DeliveryFixtures
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import ActionRequest
from workpal.delivery.models import Delivery, DeliveryArtifact
from workpal.work.models import Issue, IssueRequirements


class DeliveryConcurrency(DeliveryFixtures, TransactionTestCase):
    act = WorkpalCase.act

    def race(self, same_key):
        artifact = self.published_artifact()
        payload = dict(subject=self.subject, requirements_revision=1, summary='Concurrent result',
                       artifact_ids=[artifact['id']],
                       evidence=[dict(criterion_key='documented', artifact_ids=[artifact['id']])])
        issues_before = list(Issue.objects.values())
        requirements_before = list(IssueRequirements.objects.values())
        barrier = Barrier(2)
        def run(index):
            connections.close_all()
            try:
                connection = connections['default']
                connection.ensure_connection()
                identity = id(connection.connection)
                barrier.wait(timeout=10)
                result = registry.execute(self.actor, ActionRequest('delivery.submit', payload, None,
                    'same' if same_key else str(index)))
                return identity, result.data
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, (0, 1)))
        self.assertNotEqual(results[0][0], results[1][0])
        count = 1 if same_key else 2
        for model in (Delivery, DeliveryArtifact):
            self.assertEqual(model.objects.count(), count)
        for model in (AuditEvent, Outbox, IdempotencyResult):
            self.assertEqual(model.objects.filter(action_id='delivery.submit').count(), count)
        self.assertEqual(sorted(Delivery.objects.values_list('number', flat=True)), list(range(1, count + 1)))
        self.assertEqual(list(Issue.objects.values()), issues_before)
        self.assertEqual(list(IssueRequirements.objects.values()), requirements_before)
        return results[0][1], results[1][1]

    def test_same_key_commits_one_submission_across_two_real_connections(self):
        first, second = self.race(True)
        self.assertEqual(first, second)

    def test_distinct_keys_get_distinct_consecutive_versions_across_two_connections(self):
        first, second = self.race(False)
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual({first['number'], second['number']}, {1, 2})
