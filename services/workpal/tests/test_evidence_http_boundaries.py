"""Independent real HTTP identity, isolation and upload side-effect review."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlencode
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from tests import test_evidence_http as fixture
from workpal.identity.models import Membership
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.access.service import register_object
from workpal.contracts import ObjectRef, ActionRequest
from workpal.actions.registry import execute
from workpal.investigation.models import Source, Investigation


class EvidenceHTTPBoundaryTests(TestCase):
    setUp = fixture.EvidenceHTTPTests.setUp
    post = fixture.EvidenceHTTPTests.post
    snapshot = fixture.EvidenceHTTPTests.snapshot

    def read(self, row):
        return self.client.get(f"/api/v1/evidence/{row['id']}?workspace_id={self.actor.workspace_id}")

    def denied(self, operation, status):
        before = self.snapshot()
        response = operation()
        self.assertEqual(response.status_code, status, response.content)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(before, self.snapshot())

    def test_identity_and_independent_upstream(self):
        Membership.objects.filter(user_id=self.actor.user_id).update(role='member')
        row = self.post().json()
        self.assertEqual(self.read(row).status_code, 200)
        anonymous = Client(enforce_csrf_checks=True)
        token = anonymous.get('/api/v1/auth/csrf').json()['csrf_token']
        self.denied(lambda: anonymous.post(self.url, b'x', content_type='application/octet-stream', HTTP_X_CSRFTOKEN=token, HTTP_IDEMPOTENCY_KEY='anon'), 403)
        self.denied(lambda: anonymous.get(f"/api/v1/evidence/{row['id']}?workspace_id={self.actor.workspace_id}"), 403)
        self.denied(lambda: self.client.post(self.url, b'x', content_type='application/octet-stream', HTTP_HOST='evil.invalid', HTTP_X_CSRFTOKEN=self.token, HTTP_IDEMPOTENCY_KEY='host'), 400)
        user = get_user_model().objects.get(pk=self.actor.user_id)
        user.is_active = False; user.save()
        self.denied(lambda: self.post(), 403)
        self.denied(lambda: self.read(row), 403)
        user.is_active = True; user.save()
        old = self.token
        response = self.client.post('/api/v1/auth/login', json.dumps(dict(username=user.username,password='test-password')), content_type='application/json', HTTP_X_CSRFTOKEN=old)
        self.assertEqual(response.status_code, 200)
        self.token = self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.denied(lambda: self.client.post(self.url,b'hello',content_type='application/octet-stream',HTTP_X_CSRFTOKEN=old,HTTP_IDEMPOTENCY_KEY='http'),403)
        root = ObjectRef('http-private-root', '1')
        register_object(self.actor.workspace_id, root, is_source=True)
        obj = RegisteredObject.objects.get(kind=root.kind,object_id=root.id)
        grant = SourceGrant.objects.create(user_id=self.actor.user_id,source=obj,read=True)
        register_object(self.actor.workspace_id,ObjectRef('evidence_source',str(self.source)),[root])
        self.assertEqual(self.post().status_code,200)
        grant.read=False; grant.save()
        self.denied(lambda:self.post(),403)
        self.denied(lambda:self.read(row),403)
        grant.read=True; grant.save()
        self.assertEqual(self.post().status_code,200)
        self.assertEqual(self.read(row).status_code,200)

    def test_real_service_environment_and_two_workspace_mismatches(self):
        from workpal.contracts import Actor
        from workpal.identity.models import Workspace
        def call(actor,name,payload,key):
            return execute(actor,ActionRequest(name,payload,None,key)).data['id']
        original=self.url
        source=Source.objects.get(pk=self.source)
        wrong_service=call(self.actor,'environment_service.create',dict(environment_id=source.environment_id,name='wrong'),'wrong')
        env=call(self.actor,'environment.create',dict(project_id=source.environment.project_id,name='other',timezone='UTC'),'other')
        svc=call(self.actor,'environment_service.create',dict(environment_id=env,name='other'),'other-svc')
        for environment,service,key in ((source.environment_id,wrong_service,'bad-service'),(env,svc,'bad-env')):
            sid=call(self.actor,'evidence_source.create_upload',dict(environment_id=environment,name=key,allowed_services=[service]),key)
            self.url=original.replace(f'source_id={self.source}',f'source_id={sid}')
            self.denied(lambda:self.post(),403)
        w=Workspace.objects.create(name='real-second')
        Membership.objects.create(user_id=self.actor.user_id,workspace=w,role='owner')
        other=Actor(self.actor.user_id,w.pk)
        p=call(other,'project.create',dict(name='second'),'p2')
        e=call(other,'environment.create',dict(project_id=p,name='second',timezone='UTC'),'e2')
        s=call(other,'environment_service.create',dict(environment_id=e,name='second'),'s2')
        sid=call(other,'evidence_source.create_upload',dict(environment_id=e,name='second',allowed_services=[s]),'src2')
        inv=call(other,'investigation.start',dict(project_id=p,environment_id=e,service_id=s,problem='Second',key='i2'),'i2')
        Membership.objects.filter(user_id=self.actor.user_id).update(role='member')
        self.url=original
        row=self.post().json(); self.assertEqual(self.read(row).status_code,200)
        for url in (original.replace(f'workspace_id={self.actor.workspace_id}',f'workspace_id={w.pk}'),original.replace(f'source_id={self.source}',f'source_id={sid}'),original.replace(f'/{self.inv}/',f'/{inv}/')):
            self.url=url; self.denied(lambda:self.post(),404)
        self.denied(lambda:self.client.get(f"/api/v1/evidence/{row['id']}?workspace_id={w.pk}"),404)

    def test_time_validation_and_eleven_uploads_without_query_or_file_effects(self):
        original=self.url
        valid=dict(timezone='Asia/Shanghai',range_start='2026-11-20T01:00:00+08:00',range_end='2026-11-20T02:00:00+08:00')
        invalid=[dict(timezone='Unknown/Nowhere'),dict(range_start='',range_end=''),dict(range_start=valid['range_start']),dict(range_end=valid['range_end']),dict(valid,range_start='2026-11-20T01:00:00'),dict(valid,range_start=valid['range_end']),dict(valid,range_start='2026-11-21T01:00:00+08:00'),dict(valid,range_start='x'*65),dict(valid,range_start='2026-02-30T01:00:00+08:00')]
        for params in invalid:
            self.url=original+'&'+urlencode(params)
            self.denied(lambda:self.post(key='invalid'),400)
        before=self.snapshot()
        investigation=list(Investigation.objects.values())
        with TemporaryDirectory(prefix='workpal-boundary-') as directory, override_settings(FILE_UPLOAD_TEMP_DIR=directory), patch('django.core.files.uploadedfile.TemporaryUploadedFile',side_effect=AssertionError('temporary raw upload')), patch('django.core.files.uploadhandler.TemporaryUploadedFile',side_effect=AssertionError('temporary handler')):
            self.url=original+'&'+urlencode(valid)
            for i in range(11):
                response=self.post(b'SECRET-literal boundary',key=f'eleven-{i}')
                self.assertEqual(response.status_code,200,response.content)
                self.assertNotIn('SECRET-literal',str(response.json()))
                self.assertEqual(self.read(response.json()).json()['content'],'[REDACTED] boundary')
            self.assertEqual(list(Path(directory).iterdir()),[])
        self.assertEqual(list(Investigation.objects.values()),investigation)
        from workpal.investigation import service
        self.assertEqual(service.read(self.actor,self.inv)['query_budget'],10)
        after=self.snapshot()
        for label in before:
            if any(word in label.lower() for word in ('artifact','blob','upload')):
                self.assertEqual(before[label],after[label],label)
        for label in ('actions.IdempotencyResult','audit.AuditEvent','audit.Outbox'):
            self.assertNotIn('SECRET-literal',str(after[label]))
        # query_budget is a public fixed display; there is no query ledger here.
