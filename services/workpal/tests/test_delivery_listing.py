from tests.support import WorkpalCase
from tests.test_delivery import DeliveryFixtures

class DeliveryListing(DeliveryFixtures, WorkpalCase):
    def test_registry_empty_page(self):
        result = self.act(self.actor, 'delivery.list', {'subject': self.subject})
        self.assertEqual(result.data, {'items': [], 'next_cursor': 0})
