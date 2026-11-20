"""Artifact behavior through the public Registry seam."""
from tests.support import WorkpalCase
from tests.access_support import AccessFixtures


class ArtifactRegistry(AccessFixtures, WorkpalCase):
    def test_begin_returns_open_upload_metadata(self):
        result = self.act(self.actor, 'artifact.upload.begin',
                          {'filename': 'notes.txt', 'size': 0}, key='begin')
        self.assertEqual(result.state, 'completed')
        self.assertEqual(result.data['filename'], 'notes.txt')
        self.assertEqual(result.data['size'], 0)
        self.assertEqual(result.data['offset'], 0)
        self.assertEqual(result.data['status'], 'open')
        self.assertEqual(result.data['artifact_id'], 0)
        self.assertEqual(result.data['media_type'], 'application/octet-stream')

    def test_replay_events_and_read_has_no_outbox(self):
        from workpal.audit.models import AuditEvent, Outbox
        from workpal.delivery.models import Upload
        payload = {'filename': 'x', 'size': 0}
        first = self.act(self.actor, 'artifact.upload.begin', payload, key='unique')
        second = self.act(self.actor, 'artifact.upload.begin', payload, key='unique')
        self.assertEqual(first.data, second.data)
        self.assertEqual(Upload.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)
        self.assertEqual(Outbox.objects.count(), 1)
        self.assertEqual(self.act(self.actor, 'artifact.upload.read', {'upload_id': first.data['id']}).data, first.data)
        self.assertEqual(Outbox.objects.count(), 1)
