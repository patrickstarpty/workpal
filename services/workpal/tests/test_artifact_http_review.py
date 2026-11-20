import hashlib
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import Client
from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor
from workpal.delivery import artifacts
from workpal.delivery.models import UploadChunk
from workpal.identity.models import Membership


class ArtifactHTTPReview(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.csrf = self.client.get('/api/v1/auth/csrf').json()['csrf_token']

    def snapshot(self):
        return {m._meta.label: list(m.objects.order_by('pk').values()) for m in apps.get_models()}

    def upload(self, data, sources=(), actor=None, key='begin', **fields):
        return self.act(actor or self.actor, 'artifact.upload.begin', {'filename': 'payload.bin', 'size': len(data),
            'source_refs': [{'kind': ref.kind, 'id': ref.id} for ref in sources], **fields}, key=key).data

    def finish(self, upload, data, actor=None, key='finish'):
        return self.act(actor or self.actor, 'artifact.upload.finish',
                        {'upload_id': upload['id'], 'sha256': hashlib.sha256(data).hexdigest()}, key=key).data

    def put(self, upload, data, offset=0, workspace=None, **headers):
        workspace = self.workspace.pk if workspace is None else workspace
        headers.setdefault('HTTP_X_CSRFTOKEN', self.csrf)
        return self.client.put(f"/api/v1/artifact-uploads/{upload['id']}/chunks?workspace_id={workspace}&offset={offset}",
                               data, content_type='application/octet-stream', **headers)

    def get(self, artifact, offset=0, length=None, workspace=None, client=None):
        workspace = self.workspace.pk if workspace is None else workspace
        url = f"/api/v1/artifacts/{artifact['id']}/chunks?workspace_id={workspace}&offset={offset}"
        if length is not None:
            url += f'&length={length}'
        return (client or self.client).get(url)

    def protected_headers(self, response):
        self.assertIn('no-store', response.get('Cache-Control', ''))
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_middleware_csrf_rejection_is_not_cacheable(self):
        upload = self.upload(b'abc')
        before = self.snapshot()
        for token in ('', 'bad-token'):
            response = self.put(upload, b'abc', HTTP_X_CSRFTOKEN=token)
            self.assertEqual((response.status_code, response.json()['code']), (403, 'csrf_failed'))
            self.protected_headers(response)
        self.assertEqual(self.snapshot(), before)

    def test_large_binary_roundtrip_has_bounded_headers_and_source_audit_without_block_events(self):
        self.grant(self.a, read=True, write=True)
        self.grant(self.b, read=True, write=True)
        data = b'<script>untrusted</script>\x00' + b'x' * artifacts.MAX_CHUNK
        upload = self.upload(data, sources=[self.a, self.b], filename='证据<script>.bin', media_type='text/html')
        before = (AuditEvent.objects.count(), Outbox.objects.count())
        first = self.put(upload, data[:artifacts.MAX_CHUNK])
        second = self.put(upload, data[artifacts.MAX_CHUNK:], artifacts.MAX_CHUNK)
        self.assertEqual(first.json(), {'upload_id': upload['id'], 'offset': artifacts.MAX_CHUNK})
        self.assertEqual(second.json(), {'upload_id': upload['id'], 'offset': len(data)})
        retry = self.put(upload, data[:artifacts.MAX_CHUNK])
        self.assertEqual(retry.json()['offset'], len(data))
        self.assertEqual((AuditEvent.objects.count(), Outbox.objects.count()), before)
        artifact = self.finish(upload, data)
        outbox_before = Outbox.objects.count()
        pieces = []
        for offset in (0, artifacts.MAX_CHUNK, len(data)):
            response = self.get(artifact, offset)
            self.assertEqual(response.status_code, 200, response.content)
            self.protected_headers(response)
            self.assertEqual(response['Content-Type'], 'application/octet-stream')
            self.assertEqual(response['Content-Length'], str(len(response.content)))
            self.assertEqual(response['X-Artifact-Size'], str(len(data)))
            self.assertEqual(response['X-Artifact-SHA256'], hashlib.sha256(data).hexdigest())
            self.assertEqual(response['X-Next-Offset'], str(offset + len(response.content)))
            self.assertNotIn('Content-Disposition', response)
            pieces.append(response.content)
        self.assertEqual(b''.join(pieces), data)
        self.assertEqual(Outbox.objects.count(), outbox_before)
        reads = AuditEvent.objects.filter(action_id='artifact.read')
        self.assertEqual(reads.count(), 3)
        for event in reads:
            self.assertEqual(event.fields, {'artifact_id': artifact['id']})
            for ref in (self.a, self.b, artifacts.artifact_ref(artifact['id'])):
                self.assertIn({'kind': ref.kind, 'id': ref.id}, event.scope_refs)
        self.protected_headers(first)
        self.protected_headers(second)

    def test_declared_length_and_query_validation_never_write_bytes(self):
        upload = self.upload(b'abc')
        before = self.snapshot()
        for value, expected in (('garbage', 400), ('-1', 400), ('+1', 400), ('9' * 100, 400),
                                (str(artifacts.MAX_CHUNK + 1), 413)):
            response = self.put(upload, b'abc', CONTENT_LENGTH=value)
            self.assertEqual(response.status_code, expected, response.content)
            self.protected_headers(response)
        url = f"/api/v1/artifact-uploads/{upload['id']}/chunks?"
        for query in (f'workspace_id={self.workspace.pk}&workspace_id={self.workspace.pk}&offset=0',
                      f'workspace_id={self.workspace.pk}&offset=0&length=1',
                      f'workspace_id={self.workspace.pk}', 'offset=0', 'workspace_id=0&offset=0'):
            response = self.client.put(url + query, b'abc', content_type='application/octet-stream', HTTP_X_CSRFTOKEN=self.csrf)
            self.assertEqual(response.status_code, 400, response.content)
            self.protected_headers(response)
        self.assertEqual(self.snapshot(), before)

    def test_shared_owner_cannot_cross_workspace_and_pending_upload_is_not_downloadable(self):
        upload = self.upload(b'abc')
        response = self.get({'id': upload['id']})
        self.assertEqual((response.status_code, response.json()['code']), (404, 'not_found'))
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        other = Actor(self.user.pk, self.other.pk)
        foreign = self.upload(b'abc', actor=other)
        before = self.snapshot()
        response = self.put(foreign, b'abc')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.put(foreign, b'abc', workspace=self.other.pk).status_code, 200)
        artifact = self.finish(foreign, b'abc', actor=other)
        response = self.get(artifact)
        self.assertEqual(response.status_code, 404)
        self.protected_headers(response)
        self.assertEqual(self.get(artifact, workspace=self.other.pk).content, b'abc')

    def test_other_owner_has_read_only_artifact_access_and_revocation_stops_next_chunk(self):
        self.grant(self.a, read=True, write=True)
        upload = self.upload(b'abcdef', sources=[self.a])
        self.assertEqual(self.put(upload, b'abcdef').status_code, 200)
        artifact = self.finish(upload, b'abcdef')
        draft = self.upload(b'abcdef', sources=[self.a], key='draft')
        user = get_user_model().objects.create(username='artifact-reader')
        Membership.objects.create(user=user, workspace=self.workspace, role='owner')
        grant = SourceGrant.objects.create(user=user,
            source=RegisteredObject.objects.get(kind=self.a.kind, object_id=self.a.id), read=True, write=False)
        reader = Client(enforce_csrf_checks=True)
        reader.force_login(user)
        token = reader.get('/api/v1/auth/csrf').json()['csrf_token']
        url = f"/api/v1/artifact-uploads/{draft['id']}/chunks?workspace_id={self.workspace.pk}&offset=0"
        response = reader.put(url, b'abcdef', content_type='application/octet-stream', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.get(artifact, length=3, client=reader).content, b'abc')
        grant.read = False
        grant.save()
        count = AuditEvent.objects.count()
        for offset in (0, 3):
            response = self.get(artifact, offset, length=3, client=reader)
            self.assertEqual(response.status_code, 403)
            self.protected_headers(response)
            self.assertNotIn(b'abcdef', response.content)
        self.assertEqual(AuditEvent.objects.count(), count)

    def test_chunk_insert_failure_rolls_back_before_http_error_and_original_offset_retries(self):
        upload = self.upload(b'abc')
        original = UploadChunk.objects.create
        def fail_after_insert(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('private-upload-bytes')
        before = self.snapshot()
        with patch.object(UploadChunk.objects, 'create', fail_after_insert):
            response = self.put(upload, b'abc')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b'private-upload-bytes', response.content)
        self.protected_headers(response)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.put(upload, b'abc').json()['offset'], 3)

    def test_failure_after_binary_read_rolls_back_access_audit_without_releasing_bytes(self):
        data = b'private-binary-payload'
        upload = self.upload(data)
        self.assertEqual(self.put(upload, data).status_code, 200)
        artifact = self.finish(upload, data)
        original = artifacts.read_chunk
        def fail_after_read(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('private-binary-payload')
        before = self.snapshot()
        with patch.object(artifacts, 'read_chunk', fail_after_read):
            response = self.get(artifact)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(data, response.content)
        self.assertNotIn('X-Artifact-SHA256', response)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.protected_headers(response)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.get(artifact).content, data)

    def test_invalid_download_range_rolls_back_read_audit_and_errors_remain_nostore(self):
        upload = self.upload(b'abc')
        self.assertEqual(self.put(upload, b'abc').status_code, 200)
        artifact = self.finish(upload, b'abc')
        before = self.snapshot()
        for offset in (4, '9223372036854775808', 'true'):
            response = self.get(artifact, offset)
            self.assertEqual(response.status_code, 400)
            self.protected_headers(response)
        self.assertEqual(self.snapshot(), before)
