from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase
from tests.support import WorkpalCase
from tests.test_issue_state_review import StateFixtures
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.actions.registry import execute
from workpal.audit.models import AuditEvent, Outbox
from workpal.collaboration import service
from workpal.collaboration.models import Notification
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.identity.models import Membership
from workpal.work import issues
from workpal.work.models import IssueTransition


class NotificationFixtures(StateFixtures):
    def setUp(self):
        super().setUp()
        self.target = get_user_model().objects.create(username='decision-owner')
        self.target_membership = Membership.objects.create(user=self.target, workspace=self.workspace, role='member')
        self.recipient = Actor(self.target.pk, self.workspace.pk)

    def snapshot(self):
        return {model._meta.label: list(model.objects.order_by('pk').values()) for model in apps.get_models()}

    def fail_after_notification(self, *args, **kwargs):
        result = self.original_register(*args, **kwargs)
        if args[1].kind == 'notification':
            raise DomainError('unavailable', 'Try again.', status=503)
        return result


class IssueNotificationReview(NotificationFixtures, WorkpalCase):
    def test_agent_self_assignment_notifies_but_human_self_assignment_does_not(self):
        agent = Actor(self.user.pk, self.workspace.pk, executor_id='agent')
        payload = {'issue_id': self.issue['id'], 'assignee_user_id': self.user.pk}
        assigned = self.act(agent, 'issue.update', payload, key='agent-assign', revision=1).data
        notice = self.act(self.actor, 'inbox.list', {}).data['items'][0]
        self.assertEqual((notice['kind'], notice['comment_id']), ('assignment', 0))
        marked = self.act(self.actor, 'inbox.mark_read', {'notification_id': notice['id']}, key='read', revision=1).data
        service.notify_assignment(agent, assigned['id'], assigned['revision'])
        self.assertEqual(self.act(self.actor, 'inbox.list', {}).data['items'], [marked])
        self.assertEqual(self.act(agent, 'issue.update', payload, key='agent-assign', revision=1).data, assigned)
        cleared = issues.update(self.actor, assigned['id'], 2, assignee_user_id=0)
        issues.update(self.actor, assigned['id'], cleared['revision'], assignee_user_id=self.user.pk)
        self.assertEqual(Notification.objects.count(), 1)

    def test_custom_blocked_state_notifies_and_replay_does_not_reblock_or_unread(self):
        working = self.move(self.issue, 'working')
        self.assertFalse(Notification.objects.exists())
        blocked = self.move(working, 'hold', key='block', reason='Need decision',
                            blocked_owner_user_id=self.target.pk)
        notice = self.act(self.recipient, 'inbox.list', {}).data['items'][0]
        self.assertEqual((notice['issue_id'], notice['kind'], notice['comment_id']),
                         (self.issue['id'], 'blocked', 0))
        marked = self.act(self.recipient, 'inbox.mark_read', {'notification_id': notice['id']}, key='read', revision=1).data
        released = self.move(blocked, 'working', key='release', reason='Decision received')
        self.assertEqual(self.move(working, 'hold', key='block', reason='Need decision',
                                   blocked_owner_user_id=self.target.pk), blocked)
        self.assertEqual(issues.read(self.actor, released['id']), released)
        self.assertEqual(self.act(self.recipient, 'inbox.list', {}).data['items'], [marked])
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(IssueTransition.objects.count(), 3)
        self.assertEqual(Outbox.objects.filter(action_id='issue.transition').count(), 3)

    def test_source_revocation_blocks_source_action_and_notification_replays(self):
        writer = self.grant(self.a, read=True, write=True)
        reader = SourceGrant.objects.create(user=self.target,
            source=RegisteredObject.objects.get(kind=self.a.kind, object_id=self.a.id), read=True)
        self.register(self.workspace.pk, issues.ref(self.issue['id']), [self.a])
        payload = {'issue_id': self.issue['id'], 'assignee_user_id': self.target.pk}
        self.act(self.actor, 'issue.update', payload, key='assign', revision=1)
        notice = self.act(self.recipient, 'inbox.list', {}).data['items'][0]
        self.act(self.recipient, 'inbox.mark_read', {'notification_id': notice['id']}, key='read', revision=1)
        before = self.snapshot()
        writer.write = False
        writer.save()
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, 'issue.update', payload, key='assign', revision=1)
        self.assertEqual(caught.exception.status, 403)
        reader.read = False
        reader.save()
        self.assertEqual(self.act(self.recipient, 'inbox.list', {}).data, {'items': [], 'next_cursor': 0})
        with self.assertRaises(DomainError) as caught:
            self.act(self.recipient, 'inbox.mark_read', {'notification_id': notice['id']}, key='read', revision=1)
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(list(Notification.objects.order_by('pk').values()), before['collaboration.Notification'])

    def test_create_notification_503_rolls_back_issue_requirements_and_all_events(self):
        payload = {'project_id': self.project['id'], 'title': 'Assigned task', 'assignee_user_id': self.target.pk}
        before = self.snapshot()
        self.original_register = service.register_object
        with patch.object(service, 'register_object', self.fail_after_notification):
            with self.assertRaises(DomainError) as caught:
                self.act(self.actor, 'issue.create', payload, key='assigned-create')
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        result = self.act(self.actor, 'issue.create', payload, key='assigned-create')
        self.assertEqual(result.data['assignee_user_id'], self.target.pk)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action_id='issue.create').count(), 1)
        self.assertEqual(Outbox.objects.filter(action_id='issue.create').count(), 1)

    def test_blocked_notification_503_rolls_back_status_history_and_all_events(self):
        row = self.move(self.issue, 'working')
        before = self.snapshot()
        self.original_register = service.register_object
        with patch.object(service, 'register_object', self.fail_after_notification):
            with self.assertRaises(DomainError) as caught:
                self.move(row, 'hold', key='block', reason='Decision', blocked_owner_user_id=self.target.pk)
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        blocked = self.move(row, 'hold', key='block', reason='Decision', blocked_owner_user_id=self.target.pk)
        self.assertEqual(blocked['status_category'], 'blocked')
        self.assertEqual(IssueTransition.objects.count(), 2)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Outbox.objects.filter(action_id='issue.transition').count(), 2)

    def test_hook_requires_current_source_write_authority(self):
        assigned = issues.update(self.actor, self.issue['id'], 1, assignee_user_id=self.target.pk)
        self.register(self.workspace.pk, issues.ref(assigned['id']), [self.a])
        self.grant(self.a, read=True, write=False)
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            service.notify_assignment(self.actor, assigned['id'], assigned['revision'])
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)

    def test_hook_does_not_ignore_recipient_membership_failure(self):
        assigned = issues.update(self.actor, self.issue['id'], 1, assignee_user_id=self.target.pk)
        self.target_membership.delete()
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            service.notify_assignment(self.actor, assigned['id'], assigned['revision'])
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.snapshot(), before)


class ConcurrentIssueNotifications(NotificationFixtures, TransactionTestCase):
    act = WorkpalCase.act

    def race(self, blocked):
        row = self.move(self.issue, 'working') if blocked else self.issue
        action = 'issue.transition' if blocked else 'issue.update'
        payload = ({'issue_id': row['id'], 'target': 'hold', 'reason': 'Decision',
                    'blocked_owner_user_id': self.target.pk} if blocked else
                   {'issue_id': row['id'], 'assignee_user_id': self.target.pk})
        audits_before = AuditEvent.objects.filter(action_id=action).count()
        outbox_before = Outbox.objects.count()
        barrier = Barrier(2)
        def invoke(_):
            connections.close_all()
            try:
                connection = connections['default']
                connection.ensure_connection()
                identity = id(connection.connection)
                barrier.wait(timeout=10)
                result = execute(self.actor, ActionRequest(action, payload, row['revision'], 'same'))
                return identity, result.data
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(invoke, range(2)))
        self.assertNotEqual(results[0][0], results[1][0])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Notification.objects.get().kind, 'blocked' if blocked else 'assignment')
        self.assertEqual(issues.read(self.actor, row['id'])['revision'], row['revision'] + 1)
        self.assertEqual(AuditEvent.objects.filter(action_id=action).count(), audits_before + 1)
        self.assertEqual(Outbox.objects.count(), outbox_before + 1)

    def test_concurrent_assignment_same_key_sends_one_notice(self):
        self.race(False)

    def test_concurrent_custom_blocked_same_key_sends_one_notice(self):
        self.race(True)
