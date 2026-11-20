from django.test import TestCase
from tests import test_evidence_persistence as persistence
from workpal.investigation import evidence

class EvidencePolicyRaceTests(TestCase):
    setUp=persistence.EvidencePersistenceTests.setUp
    _upload=persistence.EvidencePersistenceTests._upload

    def test_prepared_policy_switch_cleanup_and_retry(self):
        from unittest.mock import patch
        from workpal.actions import registry
        from workpal.contracts import DomainError
        from workpal.investigation.models import EvidenceSnapshot
        evidence.configure_policy(self.actor,self.source,self.policy,1)
        old=self._upload(key='old')
        original=registry.execute
        def switch(actor,request):
            if request.action_id=='evidence.upload':
                evidence.configure_policy(actor,self.source,dict(self.policy,redact_literals=[]),2)
            return original(actor,request)
        with patch.object(registry,'execute',side_effect=switch):
            with self.assertRaises(DomainError) as error: self._upload(key='race')
        self.assertEqual(error.exception.status,409)
        self.assertFalse(EvidenceSnapshot.objects.filter(key='race').exists())
        self.assertIsNone(evidence._prepared.get())
        self.assertEqual(self._upload(key='race')['policy_revision'],3)
        self.assertEqual(self._upload(key='old'),old)
