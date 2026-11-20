from django.contrib.auth import get_user_model
from django.core import signing
from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.access.models import RegisteredObject
from workpal.audit.activity import SALT, list_issue_activity
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError
from workpal.identity.models import Membership
from workpal.work import service as projects


class ActivityReview(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()
        self.project = projects.create(self.actor, 'Activity')
        self.issue = self.create('Task')

    def create(self, title):
        return self.act(self.actor, 'issue.create', {'project_id': self.project['id'], 'title': title}, key=title).data

    def events(self, issue=None, actor=None, **filters):
        return self.act(actor or self.actor, 'issue.activity.list',
                        {'issue_id': (issue or self.issue)['id'], **filters}).data

    def test_dependency_and_hierarchy_changes_belong_only_to_the_primary_issue(self):
        target = self.create('Dependency and parent')
        payload = {'issue_id': self.issue['id'], 'depends_on_id': target['id']}
        self.act(self.actor, 'issue.dependency.add', payload, key='add', revision=1)
        self.act(self.actor, 'issue.dependency.remove', payload, key='remove', revision=2)
        self.act(self.actor, 'issue.set_parent', {'issue_id': self.issue['id'], 'parent_issue_id': target['id']},
                 key='parent', revision=3)
        self.assertEqual([e['action_id'] for e in self.events()['items']],
                         ['issue.create', 'issue.dependency.add', 'issue.dependency.remove', 'issue.set_parent'])
        self.assertEqual([e['action_id'] for e in self.events(target)['items']], ['issue.create'])

    def test_comment_changes_never_appear_on_an_issue_used_only_as_a_source(self):
        target = self.create('Comment subject')
        comment = self.act(self.actor, 'comment.create', {'issue_id': target['id'], 'body': 'Body',
            'source_refs': [{'kind': 'issue', 'id': str(self.issue['id'])}]}, key='comment').data
        self.act(self.actor, 'comment.update', {'comment_id': comment['id'], 'body': 'Edited'}, key='edit', revision=1)
        payload = {'comment_id': comment['id']}
        waiting = self.act(self.actor, 'comment.remove', payload, key='remove', revision=2)
        self.act(self.actor, 'comment.remove', payload, key='remove', revision=2,
                 confirmation_id=waiting.data['confirmation_id'])
        self.act(self.actor, 'comment.restore', payload, key='restore', revision=3)
        self.assertEqual([e['action_id'] for e in self.events()['items']], ['issue.create'])
        self.assertEqual([e['action_id'] for e in self.events(target)['items']],
                         ['issue.create', 'comment.create', 'comment.update', 'comment.remove', 'comment.restore'])

    def test_subscriptions_and_personal_inbox_metadata_are_excluded(self):
        user = get_user_model().objects.create(username='commenter')
        Membership.objects.create(user=user, workspace=self.workspace, role='member')
        other_actor = Actor(user.pk, self.workspace.pk)
        self.act(self.actor, 'issue.subscribe', {'issue_id': self.issue['id']}, key='subscribe')
        self.act(other_actor, 'comment.create', {'issue_id': self.issue['id'], 'body': 'Comment'}, key='comment')
        notification = self.act(self.actor, 'inbox.list', {}).data['items'][0]
        self.act(self.actor, 'inbox.mark_read', {'notification_id': notification['id']}, key='read', revision=1)
        self.act(self.actor, 'inbox.mark_unread', {'notification_id': notification['id']}, key='unread', revision=2)
        self.act(self.actor, 'issue.unsubscribe', {'issue_id': self.issue['id']}, key='unsubscribe')
        self.act(self.actor, 'issue.subscription.read', {'issue_id': self.issue['id']})
        before = Outbox.objects.count()
        self.assertEqual([e['action_id'] for e in self.events()['items']], ['issue.create', 'comment.create'])
        self.assertEqual([e['action_id'] for e in self.events(actor=other_actor)['items']], ['issue.create', 'comment.create'])
        self.assertEqual(Outbox.objects.count(), before)

    def test_workspace_isolation_and_cursor_binding_with_membership_in_both_workspaces(self):
        self.act(self.actor, 'issue.update', {'issue_id': self.issue['id'], 'title': 'Changed'}, key='update', revision=1)
        cursor = self.events(limit=1)['next_cursor']
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        actor = Actor(self.user.pk, self.other.pk)
        project = projects.create(actor, 'Other workspace')
        other = self.act(actor, 'issue.create', {'project_id': project['id'], 'title': 'Other'}, key='other').data
        self.assertEqual(len(self.events(other, actor)['items']), 1)
        before = AuditEvent.objects.count()
        with self.assertRaises(DomainError) as caught:
            self.events(other, actor, cursor=cursor)
        self.assertEqual(caught.exception.status, 400)
        with self.assertRaises(DomainError) as caught:
            self.events(actor=actor)
        self.assertEqual((caught.exception.status, caught.exception.code), (404, 'not_found'))
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_read_only_source_grant_allows_history_but_unavailable_comment_is_hidden(self):
        grant = self.grant(self.a, read=True, write=True)
        comment = self.act(self.actor, 'comment.create', {'issue_id': self.issue['id'], 'body': 'Restricted',
            'source_refs': [{'kind': self.a.kind, 'id': self.a.id}]}, key='comment').data
        grant.write = False
        grant.save()
        self.member.role = 'member'
        self.member.save()
        self.assertEqual([e['action_id'] for e in self.events()['items']], ['issue.create', 'comment.create'])
        RegisteredObject.objects.filter(kind='comment', object_id=str(comment['id'])).update(available=False)
        self.assertEqual([e['action_id'] for e in self.events()['items']], ['issue.create'])

    def test_malformed_signed_cursor_payloads_fail_as_input_errors(self):
        before = AuditEvent.objects.count()
        values = [None, {}, [], [self.workspace.pk, self.issue['id'], 'bad', 'bad'],
                  [True, self.issue['id'], '2026-11-20T00:00:00+00:00', '00000000-0000-0000-0000-000000000000'],
                  [self.workspace.pk, self.issue['id'], '2026-11-20T00:00:00', '00000000-0000-0000-0000-000000000000']]
        for value in values:
            with self.subTest(value=value):
                cursor = signing.dumps(value, salt=SALT)
                with self.assertRaises(DomainError) as caught:
                    list_issue_activity(self.actor, self.issue['id'], cursor=cursor)
                self.assertEqual((caught.exception.status, caught.exception.code), (400, 'invalid_input'))
        self.assertEqual(AuditEvent.objects.count(), before)
