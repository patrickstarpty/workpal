from unittest.mock import patch

from django.contrib.auth import get_user_model
from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.access.models import RegisteredObject, SourceLink, SourceGrant
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.collaboration import service
from workpal.collaboration.models import Comment, Subscription, Notification
from workpal.contracts import Actor, DomainError
from workpal.identity.models import Membership
from workpal.work import issues, service as projects
from workpal.work.models import Issue, IssueRequirements


class CollaborationReview(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()
        project = projects.create(self.actor, 'Project')
        self.issue = issues.create(self.actor, project['id'], 'Visible task')
        self.target = get_user_model().objects.create(username='recipient')
        self.target_member = Membership.objects.create(user=self.target, workspace=self.workspace, role='member')
        self.recipient = Actor(self.target.pk, self.workspace.pk)

    def subscribe(self):
        self.act(self.recipient, 'issue.subscribe', {'issue_id': self.issue['id']}, key='subscribe')

    def create(self, key='comment', **extra):
        return self.act(self.actor, 'comment.create',
                        {'issue_id': self.issue['id'], 'body': 'Comment body', **extra}, key=key)

    def tables(self):
        models = (Comment, Subscription, Notification, RegisteredObject, SourceLink,
                  IdempotencyResult, AuditEvent, Outbox, Issue, IssueRequirements)
        return {model.__name__: list(model.objects.order_by('pk').values()) for model in models}

    def test_archiving_issue_preserves_comment_creation_replay_but_prevents_new_comments(self):
        self.subscribe()
        comment = self.create()
        issues.archive(self.actor, self.issue['id'], 1)
        before = self.tables()
        self.assertEqual(self.create(), comment)
        self.assertEqual(self.tables(), before)
        self.assertEqual(service.read(self.actor, comment.data['id']), comment.data)
        with self.assertRaises(DomainError) as caught:
            self.create(key='new')
        self.assertEqual(caught.exception.code, 'issue_archived')
        self.assertEqual(self.tables(), before)

    def test_notification_hook_uses_persisted_comment_not_mutated_caller_instance(self):
        comment = self.create().data
        stale = Comment.objects.get(pk=comment['id'])
        stale.mention_user_ids = [self.target.pk]
        service.notify_comment(self.actor, stale)
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(Comment.objects.get(pk=comment['id']).mention_user_ids, [])

    def test_subscriber_check_unavailability_aborts_instead_of_silently_dropping_notice(self):
        self.subscribe()
        before = self.tables()
        original = service.authorize
        def unavailable(actor, *args, **kwargs):
            if actor.user_id == self.target.pk:
                raise DomainError('storage_busy', 'Try again.', status=503)
            return original(actor, *args, **kwargs)
        with patch.object(service, 'authorize', unavailable):
            with self.assertRaises(DomainError) as caught:
                self.create()
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.tables(), before)
        self.create()
        self.assertEqual(Notification.objects.count(), 1)

    def test_current_membership_and_recipient_isolation_apply_in_both_workspaces(self):
        self.subscribe()
        self.create()
        notice = self.act(self.recipient, 'inbox.list', {}).data['items'][0]
        Membership.objects.create(user=self.target, workspace=self.other, role='owner')
        foreign = Actor(self.target.pk, self.other.pk)
        for actor in (foreign, self.actor):
            self.assertEqual(self.act(actor, 'inbox.list', {}).data, {'items': [], 'next_cursor': 0})
            with self.assertRaises(DomainError) as caught:
                self.act(actor, 'inbox.mark_read', {'notification_id': notice['id']}, key='read', revision=1)
            self.assertEqual(caught.exception.status, 404)
        with self.assertRaises(DomainError):
            self.act(self.actor, 'inbox.list', {'recipient_id': self.target.pk})
        self.target_member.delete()
        with self.assertRaises(DomainError):
            self.act(self.recipient, 'inbox.list', {})
        self.create(key='skipped')
        self.assertEqual(Notification.objects.count(), 1)
        before = self.tables()
        with self.assertRaises(DomainError):
            self.create(key='invalid-mention', mention_user_ids=[self.target.pk])
        self.assertEqual(self.tables(), before)

    def test_visible_comment_and_notification_audits_retain_extra_sources(self):
        self.subscribe()
        self.grant(self.a, read=True, write=True)
        SourceGrant.objects.create(user=self.target,
            source=RegisteredObject.objects.get(kind=self.a.kind, object_id=self.a.id), read=True)
        comment = self.create(source_refs=[{'kind': self.a.kind, 'id': self.a.id}]).data
        comments = self.act(self.recipient, 'comment.list', {'issue_id': self.issue['id']})
        self.assertEqual(comments.object_refs, [service.ref(comment['id'])])
        audit = AuditEvent.objects.filter(action_id='comment.list').latest('created_at')
        self.assertIn({'kind': self.a.kind, 'id': self.a.id}, audit.scope_refs)
        first = self.act(self.recipient, 'inbox.list', {}).data['items'][0]
        issues.update(self.actor, self.issue['id'], 1, title='Current task title')
        current = self.act(self.recipient, 'inbox.list', {}).data['items'][0]
        self.assertEqual(current['issue_title'], 'Current task title')
        self.assertEqual(first['issue_title'], 'Visible task')
        stored = Notification.objects.values().get()
        self.assertFalse({'body', 'issue_title', 'comment_body'} & stored.keys())
        self.assertEqual(current['read_at'], '')
        audit = AuditEvent.objects.filter(action_id='inbox.list').latest('created_at')
        self.assertIn({'kind': self.a.kind, 'id': self.a.id}, audit.scope_refs)

    def test_late_mark_read_audit_failure_rolls_back_metadata_and_can_retry(self):
        self.subscribe()
        self.create()
        notice = self.act(self.recipient, 'inbox.list', {}).data['items'][0]
        before = self.tables()
        with patch('workpal.actions.registry.record', side_effect=RuntimeError('late audit failure')):
            with self.assertRaises(RuntimeError):
                self.act(self.recipient, 'inbox.mark_read', {'notification_id': notice['id']}, key='read', revision=1)
        self.assertEqual(self.tables(), before)
        result = self.act(self.recipient, 'inbox.mark_read', {'notification_id': notice['id']}, key='read', revision=1)
        self.assertEqual(result.data['revision'], 2)
        self.assertNotEqual(result.data['read_at'], '')
        self.assertEqual(issues.read(self.actor, self.issue['id']), self.issue)
        self.assertEqual(self.act(self.recipient, 'inbox.list', {'unread_only': True}).data,
                         {'items': [], 'next_cursor': 0})
