from django.test import Client
from tests.support import WorkpalCase
from tests.access_support import AccessFixtures


class ArtifactHTTP(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.token = self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.upload = self.act(self.actor, 'artifact.upload.begin', {'filename':'x', 'size':3}, key='begin').data['id']

    def put(self, data=b'abc', query=None, **headers):
        return self.client.put(f'/api/v1/artifact-uploads/{self.upload}/chunks?'+(query or f'workspace_id={self.workspace.pk}&offset=0'), data, content_type='application/octet-stream', HTTP_X_CSRFTOKEN=self.token, **headers)

    def test_put(self):
        self.assertEqual(self.put().status_code, 200)

    def finish(self, data=b'abc'):
        import hashlib
        if data:
            self.assertEqual(self.put(data).status_code, 200)
        return self.act(self.actor, 'artifact.upload.finish', {'upload_id':self.upload, 'sha256':hashlib.sha256(data).hexdigest()}, key='finish').data

    def get(self, artifact, offset=0, suffix=''):
        return self.client.get(f'/api/v1/artifacts/{artifact}/chunks?workspace_id={self.workspace.pk}&offset={offset}'+suffix)

    def test_roundtrip(self):
        import hashlib
        a = self.finish()
        r = self.get(a['id'], suffix='&length=2')
        s = self.get(a['id'], 2)
        self.assertEqual(r.content+s.content, b'abc')
        self.assertEqual(r['X-Artifact-SHA256'], hashlib.sha256(b'abc').hexdigest())
        self.assertEqual(r['X-Artifact-Size'], '3')
        self.assertEqual(r['Content-Length'], '2')
        self.assertEqual(r['X-Next-Offset'], '2')
        self.assertEqual(self.get(a['id'], 3).content, b'')

    def test_empty(self):
        self.upload = self.act(self.actor, 'artifact.upload.begin', {'filename':'empty','size':0}, key='empty').data['id']
        self.assertEqual(self.get(self.finish(b'')['id']).content, b'')

    def test_retry_conflict(self):
        self.assertEqual(self.put(b'a').json()['offset'], 1)
        self.assertEqual(self.put(b'bc', f'workspace_id={self.workspace.pk}&offset=1').json()['offset'], 3)
        self.assertEqual(self.put(b'a').json()['offset'], 3)
        self.assertEqual(self.put(b'x').status_code, 409)

    def test_invalid_query(self):
        from workpal.delivery.models import UploadChunk
        for tail in ['offset=-1','offset=+1','offset=1.0','offset=true','offset=','offset=9223372036854775808','offset=0&offset=0','offset=0&extra=1']:
            self.assertEqual(self.put(query=f'workspace_id={self.workspace.pk}&'+tail).status_code, 400)
        self.assertFalse(UploadChunk.objects.exists())

    def test_body_limits(self):
        self.assertEqual(self.put(b'').status_code,400)
        self.assertEqual(self.put(b'x'*262145).status_code,413)
        self.assertEqual(self.client.put(f'/api/v1/artifact-uploads/{self.upload}/chunks?workspace_id={self.workspace.pk}&offset=0', '{}', content_type='application/json', HTTP_X_CSRFTOKEN=self.token).status_code,400)

    def test_security(self):
        url = f'/api/v1/artifact-uploads/{self.upload}/chunks?workspace_id={self.workspace.pk}&offset=0'
        self.assertEqual(self.client.put(url,b'abc',content_type='application/octet-stream').status_code,403)
        self.assertEqual(self.put(HTTP_HOST='evil.invalid').status_code,400)
        self.client.logout()
        self.assertEqual(self.get(1).status_code,403)

    def test_closed(self):
        self.finish()
        self.assertEqual(self.put().status_code,409)

    def test_wrong_workspace(self):
        self.assertEqual(self.put(query=f'workspace_id={self.other.pk}&offset=0').status_code,404)

    def test_get_validation(self):
        a = self.finish()['id']
        for suffix in ['&length=0','&length=262145','&length=true','&length=1&length=2']:
            self.assertEqual(self.get(a,suffix=suffix).status_code,400)
        url=f'/api/v1/artifacts/{a}/chunks?workspace_id={self.workspace.pk}&offset=0'
        self.assertEqual(self.client.generic('GET',url,b'secret').status_code,400)
        self.assertEqual(self.client.post(url,HTTP_X_CSRFTOKEN=self.token).status_code,405)

    def test_read_rollback(self):
        from unittest.mock import patch
        from workpal.audit.models import AuditEvent, Outbox
        a=self.finish()['id']
        count=AuditEvent.objects.count()
        out=Outbox.objects.count()
        with patch('workpal.delivery.http.artifacts.read_chunk', side_effect=RuntimeError('secret')):
            r=self.get(a)
        self.assertEqual(r.status_code,500)
        self.assertNotIn(b'secret',r.content)
        self.assertEqual(AuditEvent.objects.count(),count)
        self.assertEqual(self.get(a).status_code,200)
        self.assertEqual(AuditEvent.objects.count(),count+1)
        self.assertEqual(Outbox.objects.count(),out)

    def test_append_failure_rolls_back(self):
        from unittest.mock import patch
        from workpal.delivery.models import Upload, UploadChunk
        with patch.object(UploadChunk.objects, 'create', side_effect=RuntimeError('private bytes')):
            self.assertEqual(self.put().status_code,500)
        self.assertEqual(Upload.objects.get(pk=self.upload).received,0)
        self.assertFalse(UploadChunk.objects.exists())
        self.assertEqual(self.put().status_code,200)

    def test_membership_revoked_between_reads(self):
        a=self.finish()['id']
        self.assertEqual(self.get(a).status_code,200)
        self.member.delete()
        self.assertEqual(self.get(a).status_code,404)

    def test_other_owner(self):
        from django.contrib.auth import get_user_model
        from workpal.identity.models import Membership
        other=get_user_model().objects.create(username='other')
        Membership.objects.create(user=other,workspace=self.workspace,role='member')
        a=self.finish()['id']
        self.client.force_login(other)
        self.token=self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.assertEqual(self.put().status_code,404)
        self.assertEqual(self.get(a).status_code,200)

    def test_source_revocation(self):
        grant=self.grant(self.a,read=True,write=True)
        self.upload=self.act(self.actor,'artifact.upload.begin',{'filename':'source','size':3,'source_refs':[{'kind':self.a.kind,'id':self.a.id}]},key='source').data['id']
        self.assertEqual(self.put().status_code,200)
        grant.write=False
        grant.save()
        self.assertEqual(self.put().status_code,403)
        grant.write=True
        grant.save()
        a=self.finish()['id']
        self.assertEqual(self.get(a).status_code,200)
        grant.read=False
        grant.save()
        self.assertEqual(self.get(a).status_code,403)

    def test_inactive_and_path_bounds(self):
        for identifier in ['0','9223372036854775808','true','-1','1.5']:
            self.assertEqual(self.client.get(f'/api/v1/artifacts/{identifier}/chunks?workspace_id={self.workspace.pk}&offset=0').status_code,400)
        self.user.is_active=False
        self.user.save()
        self.assertEqual(self.get(1).status_code,403)
