import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TransactionTestCase, RequestFactory
from tests.access_support import AccessFixtures
from tests import test_runtime_lease_http_flow as fixtures
from workpal.execution import leases, runtime_http
from workpal.execution.models import TaskToken
from workpal.contracts import DomainError


class LeaseHTTPBoundaryTests(AccessFixtures, TransactionTestCase):
    setUp = fixtures.LeaseHTTPFlowTests.setUp
    post = fixtures.LeaseHTTPFlowTests.post
    snapshot = fixtures.LeaseHTTPFlowTests.snapshot
    claim = fixtures.LeaseHTTPFlowTests.claim
    renew = fixtures.LeaseHTTPFlowTests.renew
    counts = fixtures.LeaseHTTPFlowTests.counts

    def safe(self, response, status):
        self.assertEqual(response.status_code, status, response.content)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def token(self):
        response = self.claim()
        self.safe(response, 200)
        self.assertTrue(response.json()['lease']['expires_at'].endswith('+00:00'))
        return response.json()['lease']['task_token']

    def test_transport_shape_and_auth(self):
        with patch.object(leases, '_verify_capabilities', return_value=True):
            token = self.token()
            before = self.snapshot()
            for url, secret, body in ((self.claim_url,self.device['runtime_token'],self.payload),
                                      (self.renew_url,token,dict(version=1,epoch=1))):
                for method in ('get','put','delete'):
                    with self.subTest(url=url,method=method):
                        self.safe(getattr(self.anon,method)(url,HTTP_AUTHORIZATION='Bearer '+secret),405)
                for raw in (b'[]', b'{"version":true}', b'{"version":1,"version":1}',
                            b'\xff', b'{"version":NaN}', b'{"version":1,"extra":"\\ud800"}'):
                    self.safe(self.post(url,raw,secret,self.anon),400)
                self.safe(self.post(url+'?x=1',body,secret,self.anon),400)
                self.safe(self.anon.post(url,body,content_type='text/plain',HTTP_AUTHORIZATION='Bearer '+secret),400)
                self.safe(self.post(url,body,secret,self.anon,HTTP_HOST='invalid.example'),400)
                for auth in ('bearer '+secret,'Bearer  '+secret,'Bearer '+secret+',x','Bearer '+secret+' '):
                    self.safe(self.anon.post(url,body,content_type='application/json',HTTP_AUTHORIZATION=auth),401)
            self.assertEqual(before,self.snapshot())
            self.safe(self.renew(token),200)

    def test_raw_size_and_length(self):
        before = self.snapshot()
        raw=json.dumps(self.payload).encode()
        for size,status in ((16384,409),(16385,413)):
            self.safe(self.post(self.claim_url,raw+b' '*(size-len(raw)),self.device['runtime_token'],self.anon),status)
        for length,status in (('-1',400),('x',400),('9'*5000,413),('0'*5000+'1',400)):
            request=RequestFactory().post(self.claim_url,b'{}',content_type='application/json',
                HTTP_AUTHORIZATION='Bearer '+self.device['runtime_token'])
            request.META['CONTENT_LENGTH']=length
            self.safe(runtime_http.claim(request),status)
        self.assertEqual(before,self.snapshot())

    def test_stream_read_is_bounded(self):
        request=RequestFactory().post(self.claim_url,b'{}',content_type='application/json',
            HTTP_AUTHORIZATION='Bearer '+self.device['runtime_token'])
        request.META.pop('CONTENT_LENGTH')
        with patch.object(request,'read',return_value=b' '*16385) as read:
            self.safe(runtime_http.claim(request),413)
        read.assert_called_once_with(16385)

    def test_denied_epoch_and_cross_run_zero_writes(self):
        with patch.object(leases,'_verify_capabilities',return_value=True):
            token=self.token(); before=self.snapshot()
            for epoch,status in ((True,400),(0,400),('1',400),(2,409)):
                self.safe(self.post(self.renew_url,dict(version=1,epoch=epoch),token,self.anon),status)
            self.safe(self.post(f'/api/runtime/v1/runs/{self.row.pk+999}/renew',dict(version=1,epoch=1),token,self.anon),404)
            self.assertEqual(before,self.snapshot())

    def test_unconsumed_renew_response_rotates_once(self):
        with patch.object(leases,'_verify_capabilities',return_value=True):
            token=self.token()
            # Do not bind, inspect content, or decode the committed response.
            self.renew(token)
            before=self.snapshot()
            self.safe(self.renew(token),401)
            self.assertEqual(before,self.snapshot())
            self.assertEqual(TaskToken.objects.count(),2)
            self.assertEqual(TaskToken.objects.filter(revoked_at=None).count(),1)
            self.counts(1,1)

    def test_exact_lease_expiry_stops_once(self):
        with patch.object(leases,'_verify_capabilities',return_value=True):
            token=self.token()
            with patch.object(leases,'_clock',return_value=self.now+timedelta(seconds=45)):
                response=self.renew(token); self.safe(response,200)
                self.assertEqual(response.json()['kind'],'stop_only')
                before=self.snapshot(); self.safe(self.renew(token),401)
                self.assertEqual(before,self.snapshot())
            self.counts(1,1)

    def test_exact_token_expiry_denies_without_writes(self):
        with patch.object(leases,'_verify_capabilities',return_value=True):
            token=self.token(); before=self.snapshot()
            with patch.object(leases,'_clock',return_value=self.now+timedelta(seconds=60)):
                self.safe(self.renew(token),401)
            self.assertEqual(before,self.snapshot())

    def test_fixed_error_projection(self):
        before=self.snapshot()
        for code,status in (('invalid_input',400),('authentication_required',401),('permission_denied',403),
                            ('not_found',404),('stale_epoch',409),('input_too_large',413),
                            ('storage_busy',503),('storage_unavailable',503),('unknown',500)):
            with patch.object(leases,'claim',side_effect=DomainError(code,'PRIVATE-SECRET',status=status)):
                response=self.claim(); self.safe(response,status)
                self.assertNotIn(b'PRIVATE-SECRET',response.content)
        with patch.object(leases,'claim',side_effect=RuntimeError('PRIVATE-SECRET')):
            self.safe(self.claim(),500)
        self.assertEqual(before,self.snapshot())
