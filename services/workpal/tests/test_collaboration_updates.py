from tests.support import WorkpalCase
from tests.access_support import AccessFixtures
from workpal.contracts import Actor, DomainError
from workpal.identity.models import Membership
from django.contrib.auth import get_user_model
from workpal.collaboration.models import Comment, Notification
from workpal.work import issues


class CollaborationUpdateFixtures:
    def prepare_notification(self):
        self.member.role = 'owner'
        self.member.save()
        project = self.act(self.actor, 'project.create', {'name': 'p'}, key='p').data
        self.task = self.act(self.actor, 'issue.create', {'project_id': project['id'], 'title': 'Task'}, key='i').data
        target = get_user_model().objects.create(username='recipient')
        Membership.objects.create(workspace=self.workspace, user=target, role='member')
        self.recipient = Actor(target.pk, self.workspace.pk)
        self.comment = self.act(self.actor, 'comment.create', {'issue_id': self.task['id'], 'body': 'hello', 'mention_user_ids': [target.pk]}, key='c').data
        return self.act(self.recipient, 'inbox.list', {}).data['items'][0]


class InboxUnread(CollaborationUpdateFixtures, AccessFixtures, WorkpalCase):
    def test_unread_cas_replay_and_business_state(self):
        n = self.prepare_notification()
        before = issues.read(self.actor, self.task['id'])
        comment = Comment.objects.values().get(pk=self.comment['id'])
        self.act(self.recipient, 'inbox.mark_read', {'notification_id': n['id']}, key='r', revision=1)
        result = self.act(self.recipient, 'inbox.mark_unread', {'notification_id': n['id']}, key='u', revision=2).data
        self.assertEqual((result['read_at'], result['revision']), ('', 3))
        self.assertEqual(result, self.act(self.recipient, 'inbox.mark_unread', {'notification_id': n['id']}, key='u', revision=2).data)
        with self.assertRaises(DomainError) as caught:
            self.act(self.recipient, 'inbox.mark_unread', {'notification_id': n['id']}, key='stale', revision=2)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(before, issues.read(self.actor, self.task['id']))
        self.assertEqual(comment, Comment.objects.values().get(pk=self.comment['id']))

    def test_other_recipient_cannot_mark_unread(self):
        n = self.prepare_notification()
        valid = self.act(self.recipient, 'inbox.mark_unread', {'notification_id': n['id']}, key='own', revision=1)
        self.assertEqual(valid.state, 'completed')
        before = Notification.objects.values().get(pk=n['id'])
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, 'inbox.mark_unread', {'notification_id': n['id']}, key='u', revision=2)
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(caught.exception.code, 'not_found')
        self.assertEqual(Notification.objects.values().get(pk=n['id']), before)

    def test_source_revocation_rejects_completed_unread_replay(self):
        from workpal.access.models import RegisteredObject, SourceGrant
        from workpal.collaboration import service
        n = self.prepare_notification()
        self.grant(self.a, read=True, write=True)
        self.register(self.workspace.pk, service.ref(self.comment['id']), [self.a])
        grant = SourceGrant.objects.create(user_id=self.recipient.user_id,
            source=RegisteredObject.objects.get(kind=self.a.kind, object_id=self.a.id), read=True)
        self.act(self.recipient, 'inbox.mark_read', {'notification_id': n['id']}, key='read', revision=1)
        self.act(self.recipient, 'inbox.mark_unread', {'notification_id': n['id']}, key='unread', revision=2)
        before = Notification.objects.values().get(pk=n['id'])
        grant.read = False
        grant.save()
        for key, revision in (('unread', 2), ('fresh', 3)):
            with self.subTest(key=key):
                with self.assertRaises(DomainError) as caught:
                    self.act(self.recipient, 'inbox.mark_unread', {'notification_id': n['id']}, key=key, revision=revision)
                self.assertEqual(caught.exception.status, 403)
                self.assertEqual(caught.exception.code, 'permission_denied')
        self.assertEqual(Notification.objects.values().get(pk=n['id']), before)
