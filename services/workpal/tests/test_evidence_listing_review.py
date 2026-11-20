from django.test import TestCase
from tests import test_evidence_listing as fixtures
from workpal.actions.registry import execute
from workpal.contracts import ActionRequest
from workpal.investigation import evidence


class EvidenceListingReviewTests(TestCase):
    setUp = fixtures.EvidenceListingTests.setUp
    _upload = fixtures.EvidenceListingTests._upload

    def test_registry_default_pagination_matches_public_interface(self):
        evidence.configure_policy(self.actor, self.source, self.policy, 1)
        row = self._upload()
        result = execute(self.actor, ActionRequest('evidence.list',
            dict(investigation_id=row['investigation_id']), None, None)).data
        self.assertEqual(result, evidence.list_evidence(self.actor, row['investigation_id']))
        self.assertEqual(result, dict(items=[row], next_cursor=0))
