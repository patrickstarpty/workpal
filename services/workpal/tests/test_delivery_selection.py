from tests.test_delivery import DeliveryFixtures
from tests.support import WorkpalCase

class DeliverySelectionCore(DeliveryFixtures, WorkpalCase):
    def test_empty(self):
        from workpal.delivery.models import DeliveryCurrent, DeliverySelection
        from workpal.audit.models import Outbox
        before=Outbox.objects.count()
        self.assertEqual(self.act(self.actor,'delivery.current.read',dict(subject=self.subject)).data,
            dict(subject=self.subject,revision=1,current_delivery_id=0,current_delivery_number=0))

        self.assertFalse(DeliveryCurrent.objects.exists())
        self.assertFalse(DeliverySelection.objects.exists())
        self.assertEqual(Outbox.objects.count(),before)

    def submit(self,key):
        return self.act(self.actor,'delivery.submit',dict(subject=self.subject,requirements_revision=1,summary=key),key=key).data

    def choose(self,delivery,key,revision):
        return self.act(self.actor,'delivery.select_current',dict(delivery_id=delivery['id'],reason='Reviewed by the human'),key=key,revision=revision).data

    def test_selection_candidates_cas_replay_and_snapshots(self):
        from workpal.delivery.models import Delivery, DeliveryCurrent, DeliverySelection
        from workpal.work.models import Issue
        from workpal.contracts import DomainError
        first=self.submit('first')
        issue_before=list(Issue.objects.values())
        first_before=Delivery.objects.get(pk=first['id']).__dict__.copy()
        first_before.pop('_state')
        selected=self.choose(first,'select-first',1)
        self.assertEqual(selected['revision'],2)
        event=DeliverySelection.objects.get()
        self.assertEqual((event.actor_id,event.reason,event.before_delivery_id,event.after_delivery_id),
            (self.user.pk,'Reviewed by the human',None,first['id']))
        second=self.submit('second')
        self.assertEqual(self.act(self.actor,'delivery.current.read',dict(subject=self.subject)).data,selected)
        newer=self.choose(second,'select-second',2)
        with self.assertRaises(DomainError): self.choose(first,'stale',2)
        self.assertEqual(self.choose(first,'select-first',1),selected)
        self.assertEqual(self.act(self.actor,'delivery.current.read',dict(subject=self.subject)).data,newer)
        self.assertEqual(DeliverySelection.objects.count(),2)
        self.assertEqual(DeliveryCurrent.objects.count(),1)
        self.assertEqual(list(Issue.objects.values()),issue_before)
        after=Delivery.objects.get(pk=first['id']).__dict__.copy(); after.pop('_state')
        self.assertEqual(after,first_before)

    def test_human_and_sources_on_execution_and_replay(self):
        from workpal.contracts import Actor, DomainError
        from workpal.access.models import SourceGrant
        target=self.submit('target')
        self.choose(target,'chosen',1)
        executor=Actor(self.user.pk,self.workspace.pk,executor_id='agent')
        self.assertEqual(self.act(executor,'delivery.current.read',dict(subject=self.subject)).data['revision'],2)
        for key in ['chosen','new']:
            with self.assertRaises(DomainError):
                self.act(executor,'delivery.select_current',dict(delivery_id=target['id'],reason='Reviewed by the human'),key=key,revision=1)
        SourceGrant.objects.filter(user=self.user,source__object_id=self.a.id).delete()
        with self.assertRaises(DomainError): self.choose(target,'chosen',1)
        with self.assertRaises(DomainError): self.act(self.actor,'delivery.current.read',dict(subject=self.subject))

    def test_invalid_selection_inputs(self):
        from workpal.contracts import DomainError
        target=self.submit('target')
        for reason,revision in [('',1),(' ',1),('x'*4001,1),('ok',None),('ok',True),('ok',0)]:
            with self.subTest(reason=reason[:10],revision=revision), self.assertRaises(DomainError):
                self.act(self.actor,'delivery.select_current',dict(delivery_id=target['id'],reason=reason),key='bad',revision=revision)
