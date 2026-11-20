from tests.support import WorkpalCase
from tests.test_delivery_selection_review import SelectionFixtures


class SelectionHistory(SelectionFixtures, WorkpalCase):
    def history(self, **extra):
        return self.act(self.actor, 'delivery.selections.list', dict(subject=self.subject, **extra))

    def test_empty_registry_history(self):
        self.assertEqual(self.history().data, dict(items=[], next_cursor=0))

    def test_versions_and_pagination_remain_immutable(self):
        first, second = self.submit('first'), self.submit('second')
        self.choose(first, 'one', 1, reason='first reason')
        old = self.history().data['items'][0]
        self.choose(second, 'two', 2, reason='second reason')
        page = self.history(limit=1).data
        self.assertEqual(page['items'], [old])
        tail = self.history(cursor=page['next_cursor']).data
        self.assertEqual(tail['next_cursor'], 0)
        item = tail['items'][0]
        self.assertEqual((old['before_delivery_id'], old['before_delivery_number']), (0, 0))
        self.assertEqual((item['before_delivery_id'], item['after_delivery_id']), (first['id'], second['id']))
        self.assertEqual((item['before_delivery_number'], item['after_delivery_number']), (first['number'], second['number']))
        self.assertEqual(item['actor_user_id'], self.user.pk)
        self.assertEqual(item['reason'], 'second reason')

    def test_private_current_keeps_early_public_history(self):
        from workpal.access.models import SourceGrant
        public = self.submit('public')
        private = self.submit('private', artifact_ids=[self.published_artifact()['id']])
        self.choose(public, 'one', 1)
        visible = self.history().data['items']
        self.choose(private, 'two', 2)
        self.choose(public, 'three', 3)
        grant = SourceGrant.objects.get(user=self.user, source__kind=self.b.kind, source__object_id=self.b.id)
        grant.read = False
        grant.save()
        self.assertEqual(self.history(limit=1).data, dict(items=visible, next_cursor=0))

    def test_strict_inputs(self):
        from workpal.contracts import DomainError, SubjectRef
        from workpal.delivery import selection
        from workpal.storage import MAX_SQLITE_INTEGER
        for field, values in [('cursor', [True, None, -1, '1', MAX_SQLITE_INTEGER]), ('limit', [True, None, 0, 201, '1'])]:
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(DomainError): self.history(**{field:value})
                    with self.assertRaises(DomainError):
                        selection.list_history(self.actor, SubjectRef(**self.subject), **{field:value})

    def test_metadata_query_once_and_no_outbox(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from workpal.audit.models import Outbox
        target = self.submit('target')
        self.choose(target, 'one', 1)
        before = Outbox.objects.count()
        with CaptureQueriesContext(connection) as queries:
            self.history()
        candidates = [q['sql'] for q in queries if 'FROM "delivery_deliveryselection"' in q['sql']]
        self.assertEqual(len(candidates), 1)
        for field in ('requirements_snapshot', 'workflow_snapshot', 'artifacts_snapshot', 'evidence'):
            self.assertNotIn(field, candidates[0])
        self.assertEqual(Outbox.objects.count(), before)

    def test_candidate_503_propagates_without_audit_changes(self):
        from unittest.mock import patch
        from workpal.contracts import DomainError
        from workpal.delivery import selection
        self.choose(self.submit('target'), 'one', 1)
        before = self.snapshot()
        with patch.object(selection, 'authorize', side_effect=DomainError('storage_unavailable', 'Retry', status=503)):
            with self.assertRaises(DomainError) as caught: self.history()
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)

    def test_readonly_and_archived_history(self):
        self.choose(self.submit('target'), 'one', 1)
        expected = self.history().data
        self.act(self.actor, 'issue.archive', dict(issue_id=self.issue['id']), key='archive', revision=1)
        self.member.role = 'member'
        self.member.save()
        self.assertEqual(self.history().data, expected)
