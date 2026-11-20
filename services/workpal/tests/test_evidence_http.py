"""Session transport acceptance for evidence."""
import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from tests import test_evidence_policy as fixtures
from workpal.investigation import evidence
from workpal.investigation.models import Source
from workpal.actions.registry import execute
from workpal.contracts import ActionRequest

class EvidenceHTTPTests(TestCase):
    def setUp(self):
        fixtures.EvidencePolicyTests.setUp(self)
        user=get_user_model().objects.get(pk=self.actor.user_id)
        user.set_password('test-password'); user.save()
        self.client=Client(enforce_csrf_checks=True)
        token=self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.assertEqual(self.client.post('/api/v1/auth/login',json.dumps(dict(username=user.username,password='test-password')),content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code,200)
        self.token=self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.assertNotEqual(token,self.token)
        evidence.configure_policy(self.actor,self.source,self.policy,1)
        source=Source.objects.get(pk=self.source)
        self.inv=execute(self.actor,ActionRequest('investigation.start',dict(project_id=source.environment.project_id,environment_id=source.environment_id,service_id=source.allowed_services.get().pk,problem='HTTP',key='fixture'),None,'fixture')).data['id']
        self.url=f'/api/v1/investigations/{self.inv}/evidence-uploads?workspace_id={self.actor.workspace_id}&source_id={self.source}&format=text'
    def post(self,body=b'hello',key='http'):
        return self.client.post(self.url,body,content_type='application/octet-stream',HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY=key)
    def test_binary_two_mib_session_csrf_roundtrip(self):
        response=self.post(b'x'*2097152)
        self.assertEqual(response.status_code,200)
        import hashlib
        metadata=response.json()
        self.assertEqual(metadata['raw_sha256'],hashlib.sha256(b'x'*2097152).hexdigest())
        read=self.client.get(f"/api/v1/evidence/{metadata['id']}?workspace_id={self.actor.workspace_id}")
        self.assertEqual(read.status_code,200)
        self.assertIn('content',read.json())
        before=self.snapshot()
        self.assertEqual(self.post(b'x'*2097153,key='large').status_code,413)
        self.assertEqual(self.snapshot(),before)
        generic=self.client.post('/api/v1/actions/evidence.upload',b'x'*1048577,content_type='application/json',HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(generic.status_code,413)
    snapshot=fixtures.EvidencePolicyTests.snapshot

    def test_retry_conflict_and_provenance(self):
        first=self.post(b'SECRET-literal evidence').json()
        before=self.snapshot()
        self.assertEqual(self.post(b'SECRET-literal evidence').json(),first)
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.post(b'different').status_code,409)
        self.assertEqual(first['origin'],'user_upload')
        self.assertEqual(first['coverage'],'uploaded_excerpt')
        for name in ('event_time','deployment_id','commit_sha','original_location','range_start','range_end'):
            self.assertIsNone(first[name])
        from django.apps import apps
        for label in ('actions.IdempotencyResult','audit.AuditEvent','audit.Outbox'):
            self.assertNotIn('SECRET-literal',str(list(apps.get_model(label).objects.values())))

    def test_validation_and_csrf_matrix(self):
        self.assertEqual(self.client.get(self.url).status_code,405)
        self.assertEqual(self.client.post(self.url,b'x',content_type='application/octet-stream',HTTP_IDEMPOTENCY_KEY='missing').status_code,403)
        original=self.url
        for suffix in ('&workspace_id=1','&executor_id=1','&policy=x','&normalized=x'):
            self.url=original+suffix
            response=self.post()
            self.assertEqual(response.status_code,400)
            self.assertEqual(response['Cache-Control'],'no-store')
            self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.url=original
        self.assertEqual(self.post(key=' '*3).status_code,400)
        self.assertEqual(self.post(key='x'*201).status_code,400)
        self.assertEqual(self.client.post(self.url,b'x',content_type='text/plain',HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY='type').status_code,400)
        self.assertEqual(self.client.get(f'/api/v1/investigations/{self.inv}/evidence?workspace_id={self.actor.workspace_id}&limit=201').status_code,400)
        self.assertEqual(self.client.get(f'/api/v1/investigations/{self.inv}/evidence?workspace_id=01').status_code,400)

    def test_stream_preflight_and_second_authorization(self):
        from unittest.mock import patch
        from django.http import HttpRequest
        from workpal.contracts import DomainError
        with patch.object(evidence,'authorize_upload',side_effect=DomainError('permission_denied','Denied.',status=403)), patch.object(HttpRequest,'read',side_effect=AssertionError('stream read')):
            self.assertEqual(self.post().status_code,403)
        before=self.snapshot()
        with patch.object(evidence,'submit_upload',side_effect=DomainError('permission_denied','Denied.',status=403)):
            self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.snapshot(),before)

    def test_real_record_failure_and_retry(self):
        from unittest.mock import patch
        from workpal.actions import registry
        from workpal.contracts import DomainError
        original=registry.record
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise DomainError('unavailable','secret raw',status=503)
        before=self.snapshot()
        with patch.object(registry,'record',side_effect=fail):
            response=self.post(b'SECRET-literal evidence')
        self.assertEqual(response.status_code,503)
        self.assertNotIn('secret raw',response.content.decode())
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.post(b'SECRET-literal evidence').status_code,200)

    def test_ranges_normalization_listing_and_policy_retry(self):
        self.url+='&timezone=Asia%2FShanghai&range_start=2026-11-20T01%3A00%3A00%2B08%3A00&range_end=2026-11-20T02%3A00%3A00%2B08%3A00'
        first=self.post(b'SECRET-literal evidence').json()
        self.assertEqual(first['timezone'],'Asia/Shanghai')
        self.assertIsNotNone(first['range_start'])
        evidence.configure_policy(self.actor,self.source,dict(self.policy,redact_literals=[]),2)
        self.assertEqual(self.post(b'SECRET-literal evidence').json(),first)
        url=f"/api/v1/evidence/{first['id']}?workspace_id={self.actor.workspace_id}"
        read=self.client.get(url)
        self.assertEqual(read.json()['content'],'[REDACTED] evidence')
        listing=self.client.get(f'/api/v1/investigations/{self.inv}/evidence?workspace_id={self.actor.workspace_id}&cursor=0&limit=1')
        self.assertEqual(listing.json(),evidence.list_evidence(self.actor,self.inv,0,1))
        self.assertEqual(listing.json()['items'],[first])

    def test_dynamic_source_access_and_generic_forgery(self):
        first=self.post().json()
        payload=dict(workspace_id=self.actor.workspace_id,payload=dict(investigation_id=self.inv,source_id=self.source,format='text',timezone='',range_start='',range_end='',raw_sha256=first['raw_sha256'],raw_bytes=first['raw_bytes']),idempotency_key='http')
        before=self.snapshot()
        forged=self.client.post('/api/v1/actions/evidence.upload',json.dumps(payload),content_type='application/json',HTTP_X_CSRFTOKEN=self.token)
        self.assertIn(forged.status_code,(400,403))
        self.assertEqual(before,self.snapshot())
        source=Source.objects.get(pk=self.source)
        source.allowed_services.clear()
        self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.post(key='new').status_code,403)
        self.assertEqual(self.client.get(f"/api/v1/evidence/{first['id']}?workspace_id={self.actor.workspace_id}").status_code,403)

    def test_body_properties_untouched_and_length_validation(self):
        from unittest.mock import patch, PropertyMock
        from django.http import HttpRequest
        with patch.object(HttpRequest,'body',new_callable=PropertyMock,side_effect=AssertionError('body accessed')):
            self.assertEqual(self.post().status_code,200)
        from workpal.investigation.evidence_http import endpoint
        from django.test import RequestFactory
        request=RequestFactory().post(self.url,b'hello',content_type='application/octet-stream')
        request.user=get_user_model().objects.get(pk=self.actor.user_id)
        request.session=self.client.session
        request.META['HTTP_IDEMPOTENCY_KEY']='length'
        request.META['CONTENT_LENGTH']='01'
        self.assertEqual(endpoint(request,investigation_id=self.inv).status_code,400)
        request.META['CONTENT_LENGTH']='2097153'
        self.assertEqual(endpoint(request,investigation_id=self.inv).status_code,413)
