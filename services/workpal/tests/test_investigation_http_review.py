from django.test import TestCase
from workpal.actions.registry import _specs

class InvestigationActionReview(TestCase):
    def test_action_capabilities(self):
        self.assertEqual(_specs['environment.grant'].capability,'publish')
        self.assertEqual(_specs['investigation.start'].capability,'write')
        self.assertIn('source_refs',_specs['environment.create'].form_class.base_fields)
        self.assertIn('environment_id',_specs['investigation.list'].form_class.base_fields)
