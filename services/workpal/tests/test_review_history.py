from tests.support import WorkpalCase
from tests.test_review_validation import ReviewFixtures

class ReviewHistory(ReviewFixtures, WorkpalCase):
    def test_registry_history(self):
        saved = self.decide(self.ready()).data
        result = self.act(self.actor, 'review.list', dict(subject=self.subject)).data
        self.assertEqual([item['id'] for item in result['items']], [saved['id']])
        self.assertEqual(result['items'][0]['requirements_revision'], 1)
        self.assertEqual(result['next_cursor'], 0)

    def listing(self, **page):
        return self.act(self.actor, 'review.list', dict(subject=self.subject, **page))

    def test_hidden_prefix_middle_tail(self):
        from workpal.contracts import ObjectRef
        private = self.register(self.workspace.pk, ObjectRef('source', 'secret-history'), is_source=True)
        grant = self.grant(private, read=True, write=True)
        target = self.ready()
        saved = [self.decide(target, key=str(i), revision=2+i,
            source_refs=[dict(kind=private.kind,id=private.id)] if i%2==0 else []).data for i in range(5)]
        grant.read=False
        grant.save()
        first=self.listing(limit=1).data
        self.assertEqual([x['id'] for x in first['items']], [saved[1]['id']])
        last=self.listing(cursor=first['next_cursor'],limit=1).data
        self.assertEqual([x['id'] for x in last['items']], [saved[3]['id']])
        self.assertEqual(last['next_cursor'],0)

    def test_strict_inputs(self):
        from workpal.contracts import SubjectRef, DomainError
        from workpal.storage import MAX_SQLITE_INTEGER
        from workpal.delivery import review
        for field, values in [('cursor',[True,None,'0',-1,MAX_SQLITE_INTEGER]),('limit',[True,None,'1',0,201])]:
            for value in values:
                with self.subTest(field=field,value=value):
                    with self.assertRaises(DomainError): self.listing(**{field:value})
                    with self.assertRaises(DomainError): review.list_reviews(self.actor,SubjectRef(**self.subject),**{field:value})

    def test_executor_readonly_and_summary_query(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from workpal.access.models import SourceGrant
        from workpal.contracts import Actor
        from workpal.audit.models import Outbox
        saved=self.decide(self.ready()).data
        SourceGrant.objects.filter(user=self.user).update(write=False)
        self.actor=Actor(self.user.pk,self.workspace.pk,executor_id='reader')
        before=Outbox.objects.count()
        with CaptureQueriesContext(connection) as queries:
            result=self.listing()
        self.assertEqual(result.data['items'][0]['id'],saved['id'])
        self.assertEqual(Outbox.objects.count(),before)
        candidates=[q['sql'] for q in queries if 'FROM "delivery_review"' in q['sql']]
        self.assertEqual(len(candidates),1)
        self.assertNotIn('workflow_snapshot',candidates[0])
        self.assertIn('JSON_EXTRACT',candidates[0])

    def test_late_audit_failure_rolls_back(self):
        from unittest.mock import patch
        from workpal.actions import registry
        from workpal.contracts import DomainError
        self.decide(self.ready())
        before=self.snapshot()
        original=registry.record
        def broken(*args,**kwargs):
            original(*args,**kwargs)
            raise DomainError('storage_unavailable','Retry',status=503)
        with patch.object(registry,'record',broken),self.assertRaises(DomainError): self.listing()
        self.assertEqual(self.snapshot(),before)
