from django.test import TestCase
from tests import test_evidence_persistence as persistence
from workpal.actions.registry import execute
from workpal.contracts import ActionRequest
from workpal.investigation import evidence

class EvidenceListingTests(TestCase):
    setUp = persistence.EvidencePersistenceTests.setUp
    _upload = persistence.EvidencePersistenceTests._upload

    def test_registered_list(self):
        evidence.configure_policy(self.actor,self.source,self.policy,1)
        row=self._upload()
        result=execute(self.actor,ActionRequest('evidence.list',dict(investigation_id=row['investigation_id'],cursor=0,limit=50),None,None)).data
        self.assertEqual(result['items'],[row])
        self.assertEqual(result['next_cursor'],0)

    def test_twenty_one_pagination_and_empty(self):
        evidence.configure_policy(self.actor,self.source,self.policy,1)
        rows=[self._upload(key=str(i)) for i in range(21)]
        page=evidence.list_evidence(self.actor,rows[0]['investigation_id'],limit=20)
        self.assertEqual(page['items'],rows[:20])
        last=evidence.list_evidence(self.actor,rows[0]['investigation_id'],cursor=page['next_cursor'],limit=20)
        self.assertEqual(last,dict(items=rows[20:],next_cursor=0))
        self.assertEqual(evidence.list_evidence(self.actor,rows[0]['investigation_id'],cursor=rows[-1]['id']),dict(items=[],next_cursor=0))

    def test_strict_input(self):
        from workpal.contracts import DomainError
        for values in [(True,0,50),(1,True,50),(1,0,True),(1,-1,50),(1,0,0),(1,0,201)]:
            with self.assertRaises(DomainError): evidence.list_evidence(self.actor,*values)

    def test_hidden_before_paging_and_503(self):
        from unittest.mock import patch
        from workpal.contracts import DomainError
        evidence.configure_policy(self.actor,self.source,self.policy,1)
        rows=[self._upload(key=str(i)) for i in range(5)]
        original=evidence.authorize
        def filtered(actor,capability,refs):
            if any(r.kind=='evidence' and int(r.id) in [rows[i]['id'] for i in (0,2,4)] for r in refs):
                raise DomainError('permission_denied','Denied',status=403)
            return original(actor,capability,refs)
        with patch.object(evidence,'authorize',side_effect=filtered):
            self.assertEqual(evidence.list_evidence(self.actor,rows[0]['investigation_id'],limit=2)['items'],[rows[1],rows[3]])
        with patch.object(evidence,'_authorized',side_effect=DomainError('unavailable','Unavailable',status=503)):
            with self.assertRaises(DomainError) as error: evidence.list_evidence(self.actor,rows[0]['investigation_id'])
        self.assertEqual(error.exception.status,503)

    def test_sql_projection(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        evidence.configure_policy(self.actor,self.source,self.policy,1)
        row=self._upload()
        with CaptureQueriesContext(connection) as queries:
            evidence.list_evidence(self.actor,row['investigation_id'])
        sql=[q['sql'] for q in queries if 'SELECT' in q['sql'] and 'investigation_evidencesnapshot' in q['sql']]
        self.assertTrue(sql)
        for query in sql:
            projection=query.split(' FROM ')[0]
            self.assertNotIn('"content"',projection)
            self.assertNotIn('"policy"',projection)
