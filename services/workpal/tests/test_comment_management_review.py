from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from tests.test_collaboration_updates import CollaborationUpdateFixtures
from workpal.collaboration import service
from workpal.collaboration.models import Notification
from workpal.contracts import DomainError
from workpal.identity.models import Membership


class CommentManagementReview(CollaborationUpdateFixtures, AccessFixtures, WorkpalCase):
    def snapshot(self):
        return {model._meta.label: list(model.objects.order_by('pk').values())
                for model in apps.get_models()}

    def test_direct_management_rejects_malformed_and_unencodable_source_arrays(self):
        self.prepare_notification()
        for sources in (None, {}, False, '', 0, [{'kind': 'source', 'id': '\ud800'}]):
            with self.subTest(sources=sources):
                before = self.snapshot()
                revision = service.read(self.actor, self.comment['id'])['revision']
                with self.assertRaises(DomainError) as caught:
                    service.manage(self.actor, self.comment['id'], revision, 'update', source_refs=sources)
                self.assertEqual(caught.exception.status, 400)
                self.assertEqual(self.snapshot(), before)

    def test_late_recipient_503_rolls_back_prior_notification_and_edit_then_retries(self):
        self.prepare_notification()
        recipients = [get_user_model().objects.create(username=name) for name in ('first-new', 'second-new')]
        for user in recipients:
            Membership.objects.create(workspace=self.workspace, user=user, role='member')
        payload = {'comment_id': self.comment['id'], 'body': 'New body',
                   'mention_user_ids': [self.recipient.user_id, *[user.pk for user in recipients]]}
        before = self.snapshot()
        original = service.selected
        def unavailable(actor, *args, **kwargs):
            if actor.user_id == recipients[1].pk:
                raise DomainError('storage_busy', 'Try again.', status=503)
            return original(actor, *args, **kwargs)
        with patch.object(service, 'selected', unavailable):
            with self.assertRaises(DomainError) as caught:
                self.act(self.actor, 'comment.update', payload, key='edit', revision=1)
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        result = self.act(self.actor, 'comment.update', payload, key='edit', revision=1)
        self.assertEqual(result.data['revision'], 2)
        self.assertEqual(Notification.objects.count(), 3)
        self.assertEqual(self.act(self.actor, 'comment.update', payload, key='edit', revision=1), result)
        self.assertEqual(Notification.objects.count(), 3)
