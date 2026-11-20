from django.test import TestCase

from tests import test_evidence_policy as fixtures
from workpal.actions.registry import execute
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.investigation.evidence import configure_policy, read_policy


class EvidencePolicyReviewTests(TestCase):
    setUp = fixtures.EvidencePolicyTests.setUp
    request = fixtures.EvidencePolicyTests.request
    confirmed = fixtures.EvidencePolicyTests.confirmed
    snapshot = fixtures.EvidencePolicyTests.snapshot

    def test_executor_cannot_read_sensitive_management_policy(self):
        execute(self.actor, self.confirmed())
        self.assertEqual(read_policy(self.actor, self.source)['policy'], self.policy)
        request = ActionRequest('evidence_policy.read', {'source_id': self.source}, None, None)
        self.assertEqual(execute(self.actor, request).data['policy'], self.policy)
        machine = Actor(self.actor.user_id, self.actor.workspace_id, executor_id='runner')
        before = self.snapshot()
        for read in (lambda: read_policy(machine, self.source), lambda: execute(machine, request)):
            with self.subTest(interface=read):
                with self.assertRaises(DomainError) as caught:
                    read()
                self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)

    def test_executor_cannot_configure_through_direct_interface(self):
        execute(self.actor, self.confirmed())
        machine = Actor(self.actor.user_id, self.actor.workspace_id, executor_id='runner')
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            configure_policy(machine, self.source, self.policy, 2)
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
