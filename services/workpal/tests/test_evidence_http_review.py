"""Independent HTTP review; fixture methods only, no inherited test discovery."""
import io
import json
from unittest.mock import patch, PropertyMock
from django.test import TestCase, RequestFactory, Client
from django.contrib.auth import get_user_model
from tests import test_evidence_http as fixture
from workpal.access.models import SourceGrant
from workpal.identity.models import Membership
from workpal.investigation import evidence
from workpal.investigation.evidence_http import endpoint

class EvidenceHTTPReviewTests(TestCase):
    setUp = fixture.EvidenceHTTPTests.setUp
    post = fixture.EvidenceHTTPTests.post
    snapshot = fixture.EvidenceHTTPTests.snapshot

    def member(self):
        Membership.objects.filter(user_id=self.actor.user_id).update(role='member')

    def read(self, row):
        return self.client.get(f"/api/v1/evidence/{row['id']}?workspace_id={self.actor.workspace_id}")

    def direct(self, body, length=None, hook=None, key='stream'):
        request=RequestFactory().post(self.url,b'',content_type='application/octet-stream',HTTP_IDEMPOTENCY_KEY=key)
        request.META['CONTENT_TYPE']='application/octet-stream'
        request.content_type='application/octet-stream'
        request.user=get_user_model().objects.get(pk=self.actor.user_id)
        request.session=self.client.session
        request.META['CONTENT_LENGTH']='' if length is None else length
        stream=io.BytesIO(body)
        calls=[]
        def read(size):
            calls.append(size)
            chunk=stream.read(size)
            if hook: hook()
            return chunk
        request.read=read
        return request,calls

    def test_member_real_session_and_write_revocation(self):
        self.member()
        first=self.post().json()
        self.assertEqual(self.read(first).status_code,200)
        grant=SourceGrant.objects.get(user_id=self.actor.user_id,source__kind='environment')
        grant.write=False; grant.save()
        before=self.snapshot()
        for key in ('http','new'):
            response=self.post(key=key)
            self.assertEqual(response.status_code,403)
            self.assertEqual(response['Cache-Control'],'no-store')
            self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.read(first).status_code,200)
        grant.read=False; grant.save()
        self.assertEqual(self.read(first).status_code,403)
        self.assertEqual(Client().get(self.url).status_code,405)

    def test_actual_stream_lengths_and_preflight(self):
        self.member()
        for body,length,status in ((b'x'*2097152,None,200),(b'x'*2097153,None,413),(b'abc','2',400),(b'abc','4',400),(b'abc','01',400),(b'abc','+3',400)):
            request,calls=self.direct(body,length,key='len'+str(length))
            before=self.snapshot()
            response=endpoint(request,investigation_id=self.inv)
            self.assertEqual(response.status_code,status)
            self.assertTrue(all(n<=65536 for n in calls))
            if status!=200: self.assertEqual(before,self.snapshot())
        SourceGrant.objects.filter(user_id=self.actor.user_id,source__kind='environment').update(write=False)
        request,calls=self.direct(b'secret')
        self.assertEqual(endpoint(request,investigation_id=self.inv).status_code,403)
        self.assertEqual(calls,[])

    def test_actual_read_revokes_grant_before_submit(self):
        self.member()
        grant=SourceGrant.objects.get(user_id=self.actor.user_id,source__kind='environment')
        def revoke():
            grant.write=False; grant.save()
        request,calls=self.direct(b'private',hook=revoke)
        revoke(); before=self.snapshot()
        grant.write=True; grant.save()
        with patch.object(type(request),'body',new_callable=PropertyMock,side_effect=AssertionError('body')), \
             patch.object(type(request),'POST',new_callable=PropertyMock,side_effect=AssertionError('POST')), \
             patch.object(type(request),'FILES',new_callable=PropertyMock,side_effect=AssertionError('FILES')):
            response=endpoint(request,investigation_id=self.inv)
        self.assertEqual(response.status_code,403)
        self.assertTrue(calls)
        self.assertEqual(before,self.snapshot())

    def test_jsonl_policy_versions_and_unknown_facts(self):
        self.url=self.url.replace('format=text','format=jsonl')
        body=b'\n'.join(json.dumps({'message':'SECRET-literal','discard':'private'}).encode() for _ in range(1001))
        first=self.post(body).json()
        content=self.read(first).json()['content']
        self.assertEqual(len(content.splitlines()),1000)
        self.assertNotIn('discard',content)
        self.assertNotIn('SECRET-literal',content)
        for name in ('event_time','deployment_id','commit_sha','original_location'):
            self.assertIsNone(first[name])
        evidence.configure_policy(self.actor,self.source,dict(self.policy,redact_literals=[]),2)
        self.assertEqual(self.post(body).json(),first)
        second=self.post(body,key='new-policy').json()
        self.assertIn('SECRET-literal',self.read(second).json()['content'])
        self.assertNotEqual(first['policy_revision'],second['policy_revision'])

    def test_record_rollback_retry_and_get_side_effects(self):
        from workpal.actions import registry
        from workpal.contracts import DomainError
        original=registry.record
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise DomainError('unavailable','PRIVATE-REVIEW',status=503)
        before=self.snapshot()
        with patch.object(registry,'record',side_effect=fail):
            response=self.post(b'PRIVATE-REVIEW')
        self.assertEqual(response.status_code,503)
        self.assertNotIn(b'PRIVATE-REVIEW',response.content)
        self.assertEqual(before,self.snapshot())
        row=self.post(b'PRIVATE-REVIEW').json()
        before=self.snapshot()
        self.assertEqual(self.post(b'PRIVATE-REVIEW').json(),row)
        self.assertEqual(before,self.snapshot())
        for url in (f"/api/v1/evidence/{row['id']}?workspace_id={self.actor.workspace_id}",f'/api/v1/investigations/{self.inv}/evidence?workspace_id={self.actor.workspace_id}&limit=1'):
            before=self.snapshot()
            self.assertEqual(self.client.get(url).status_code,200)
            after=self.snapshot()
            for label in before:
                if label=='audit.AuditEvent': self.assertEqual(len(after[label]),len(before[label])+1)
                else: self.assertEqual(before[label],after[label],label)
