from tests.support import WorkpalCase
from tests.test_delivery_selection_review import SelectionFixtures

class Reviews(SelectionFixtures, WorkpalCase):
    def test_request_changes_and_read(self):
        target = self.submit('target')
        self.choose(target, 'chosen', 1)
        result = self.act(self.actor, 'delivery.review', dict(delivery_id=target['id'], version=1,
            decision=dict(outcome='request_changes', reason='Missing evidence.')), key='review', revision=2).data
        self.assertEqual(result['decision']['reason'], 'Missing evidence.')
        self.assertEqual(self.act(self.actor, 'review.read', dict(review_id=result['id'])).data, result)

    def decide(self, target, key='review', revision=2, outcome='approve', actor=None, version=None):
        return self.act(actor or self.actor, 'delivery.review', dict(delivery_id=target['id'],
            version=version or target['number'], decision=dict(outcome=outcome,reason='Review reason.')),
            key=key,revision=revision).data

    def test_approve_real_evidence_replay_and_immutable_facts(self):
        from workpal.delivery.models import Delivery, DeliverySelection, DeliveryCurrent, Review
        from workpal.work.models import Issue
        artifact=self.published_artifact()
        target=self.submit('target',artifact_ids=[artifact['id']],evidence=[dict(criterion_key='documented',artifact_ids=[artifact['id']])])
        self.choose(target,'chosen',1)
        before={m:list(m.objects.values()) for m in (Issue,Delivery,DeliverySelection)}
        result=self.decide(target)
        self.assertEqual(result['revision'],3)
        self.assertEqual(DeliveryCurrent.objects.get().current_delivery_id,target['id'])
        self.assertEqual(self.decide(target),result)
        self.assertEqual(Review.objects.count(),1)
        for m,rows in before.items(): self.assertEqual(list(m.objects.values()),rows)
        result['requirements_snapshot']['criteria'].clear()
        self.assertTrue(self.act(self.actor,'review.read',dict(review_id=result['id'])).data['requirements_snapshot']['criteria'])

    def test_note_only_and_empty_criteria_reject_approve(self):
        from workpal.contracts import DomainError
        from workpal.delivery.models import Delivery
        target=self.submit('target',evidence=[dict(criterion_key='documented',artifact_ids=[],note='Claim')])
        self.choose(target,'chosen',1)
        with self.assertRaises(DomainError): self.decide(target)
        row=Delivery.objects.get(pk=target['id'])
        row.requirements_snapshot['criteria']=[]
        row.save(update_fields=['requirements_snapshot'])
        with self.assertRaises(DomainError): self.decide(target)
        self.assertEqual(self.decide(target,outcome='request_changes')['decision']['outcome'],'request_changes')

    def test_version_current_revision_and_requirements_conflicts(self):
        from workpal.contracts import DomainError
        first=self.submit('first')
        second=self.submit('second')
        self.choose(first,'chosen',1)
        for target,version,revision in ((first,2,2),(second,2,2),(first,1,1)):
            with self.assertRaises(DomainError): self.decide(target,version=version,revision=revision,outcome='request_changes')
        self.act(self.actor,'issue.update',dict(issue_id=self.issue['id'],title='Changed'),key='update',revision=1)
        with self.assertRaises(DomainError): self.decide(first)
        self.assertEqual(self.decide(first,outcome='request_changes')['revision'],3)

    def test_human_role_and_replay_authorization(self):
        from workpal.contracts import Actor, DomainError
        target=self.submit('target')
        self.choose(target,'chosen',1)
        original=self.decide(target,outcome='request_changes')
        with self.assertRaises(DomainError):
            self.decide(target,actor=Actor(self.actor.user_id,self.actor.workspace_id,executor_id=1),outcome='request_changes')
        self.member.role='member'; self.member.save()
        with self.assertRaises(DomainError): self.decide(target,outcome='request_changes')
        self.assertEqual(self.act(self.actor,'review.read',dict(review_id=original['id'])).data,original)

    def test_replay_checks_sources_and_new_decisions_reject_archive(self):
        from workpal.contracts import DomainError
        from workpal.access.models import SourceGrant
        target=self.submit('target')
        self.choose(target,'chosen',1)
        original=self.decide(target,outcome='request_changes')
        self.act(self.actor,'issue.archive',dict(issue_id=self.issue['id']),key='archive',revision=1)
        self.assertEqual(self.decide(target,outcome='request_changes'),original)
        with self.assertRaises(DomainError): self.decide(target,key='new',revision=3,outcome='request_changes')
        grant=SourceGrant.objects.get(user=self.user,source__kind=self.a.kind,source__object_id=self.a.id)
        grant.write=False; grant.save()
        with self.assertRaises(DomainError): self.decide(target,outcome='request_changes')
