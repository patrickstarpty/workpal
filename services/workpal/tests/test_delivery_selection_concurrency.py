from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import connections
from django.test import TransactionTestCase
from tests.support import WorkpalCase
from tests.test_delivery_selection_review import SelectionFixtures
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import ActionRequest, DomainError
from workpal.delivery.models import DeliveryCurrent, DeliverySelection


class SelectionConcurrency(SelectionFixtures, TransactionTestCase):
    act = WorkpalCase.act

    def race(self, same_key, existing=False):
        first, second = self.submit('first'), self.submit('second')
        if existing:
            self.choose(first, 'initial', 1)
        revision = 2 if existing else 1
        before = {model: model.objects.filter(action_id='delivery.select_current').count()
                  for model in (AuditEvent, Outbox, IdempotencyResult)}
        barrier = Barrier(2)
        def run(index):
            connections.close_all()
            try:
                connection = connections['default']
                connection.ensure_connection()
                identity = id(connection.connection)
                barrier.wait(timeout=10)
                target = first if same_key or index == 0 else second
                try:
                    result = registry.execute(self.actor, ActionRequest('delivery.select_current',
                        dict(delivery_id=target['id'], reason='Concurrent choice.'), revision,
                        'same' if same_key else str(index)))
                    return identity, 200, result.data
                except DomainError as exc:
                    return identity, exc.status, exc.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, (0, 1)))
        self.assertNotEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(result[1] for result in results), [200, 200] if same_key else [200, 409])
        for model, count in before.items():
            self.assertEqual(model.objects.filter(action_id='delivery.select_current').count(), count + 1)
        self.assertEqual(DeliveryCurrent.objects.count(), 1)
        self.assertEqual(DeliveryCurrent.objects.get().revision, revision + 1)
        self.assertEqual(DeliverySelection.objects.count(), 2 if existing else 1)
        winner = next(result[2] for result in results if result[1] == 200)
        self.assertEqual(self.current().data, winner)
        if same_key:
            self.assertEqual(results[0][2], results[1][2])
        else:
            self.assertEqual(next(result[2] for result in results if result[1] == 409), 'revision_conflict')

    def test_same_key_selects_once_across_two_real_connections(self):
        self.race(True)

    def test_two_first_selections_accept_only_one_initial_revision(self):
        self.race(False)

    def test_two_switches_accept_only_one_existing_revision(self):
        self.race(False, existing=True)
