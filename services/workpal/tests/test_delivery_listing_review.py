from copy import deepcopy
from unittest.mock import patch

from django.apps import apps
from django.db import connection
from django.test.utils import CaptureQueriesContext
from tests.support import WorkpalCase
from tests.test_delivery import DeliveryFixtures
from workpal.access.models import SourceGrant
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError, ObjectRef, SubjectRef
from workpal.delivery import service
from workpal.delivery.models import Delivery
from workpal.identity.models import Membership
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work import issues, service as projects
from workpal.workflows import service as workflows


class DeliveryListReview(DeliveryFixtures, WorkpalCase):
    def submit(self, key, **extra):
        payload = dict(subject=self.subject, requirements_revision=1, summary=key)
        payload.update(extra)
        return self.act(self.actor, 'delivery.submit', payload, key=key).data

    def listing(self, actor=None, subject=None, **page):
        return self.act(actor or self.actor, 'delivery.list', dict(subject=subject or self.subject, **page))

    def snapshot(self):
        return {m._meta.label: list(m.objects.order_by('pk').values()) for m in apps.get_models()}

    def grant_row(self, source):
        return SourceGrant.objects.get(user=self.user, source__kind=source.kind, source__object_id=source.id)

    def test_hidden_prefix_middle_and_tail_do_not_consume_visible_page_slots(self):
        artifact = self.published_artifact()
        deliveries = [self.submit(str(index), artifact_ids=[artifact['id']] if index % 2 == 0 else [])
                      for index in range(5)]
        grant = self.grant_row(self.b)
        grant.read = False
        grant.save()
        before = Outbox.objects.count()
        first = self.listing(limit=1).data
        self.assertEqual([item['id'] for item in first['items']], [deliveries[1]['id']])
        self.assertEqual(first['next_cursor'], deliveries[1]['id'])
        second = self.listing(cursor=first['next_cursor'], limit=1).data
        self.assertEqual([item['id'] for item in second['items']], [deliveries[3]['id']])
        self.assertEqual(second['next_cursor'], 0)
        self.assertEqual(self.listing(cursor=deliveries[3]['id']).data, {'items': [], 'next_cursor': 0})
        self.assertEqual(set(first), {'items', 'next_cursor'})
        self.assertEqual(set(first['items'][0]), {'id', 'number', 'subject', 'source', 'submitted_by',
                         'created_at', 'summary', 'requirements_revision', 'sha256'})
        self.assertEqual(Outbox.objects.count(), before)
        grant.read = True
        grant.save()
        self.assertEqual(self.listing(limit=1).data['items'][0]['id'], deliveries[0]['id'])

    def test_readonly_sources_and_executor_can_read_with_precise_audit_scope(self):
        artifact = self.published_artifact()
        delivery = self.submit('visible', artifact_ids=[artifact['id']])
        SourceGrant.objects.filter(user=self.user).update(write=False)
        actor = Actor(self.user.pk, self.workspace.pk, executor_id='reader-agent')
        before = Outbox.objects.count()
        result = self.listing(actor)
        self.assertEqual(result.object_refs, [issues.ref(self.issue['id']), service.ref(delivery['id'])])
        self.assertEqual(result.data['items'][0]['requirements_revision'], 1)
        event = AuditEvent.objects.get(action_id='delivery.list')
        refs = {ObjectRef(**r) for r in event.scope_refs}
        self.assertTrue({self.a, self.b, issues.ref(self.issue['id']), service.ref(delivery['id'])} <= refs)
        self.assertEqual(Outbox.objects.count(), before)
        self.assertNotIn('visible', str(event.fields))

    def test_requirement_and_artifact_sources_filter_independently_subject_revoke_denies(self):
        first = self.submit('old requirements')
        old_req = first['requirements_snapshot']['id']
        issue2 = self.act(self.actor, 'issue.update', {'issue_id': self.issue['id'], 'title': 'New requirements'},
                          key='update', revision=1).data
        artifact = self.published_artifact()
        second = self.submit('new requirements', requirements_revision=issue2['requirements_revision'],
                             artifact_ids=[artifact['id']])
        private = self.register(self.workspace.pk, ObjectRef('source', 'requirements-private'), is_source=True)
        grant = self.grant(private, read=True, write=True)
        self.register(self.workspace.pk, issues.requirement_ref(old_req), [private])
        grant.read = False
        grant.save()
        self.assertEqual([d['id'] for d in self.listing().data['items']], [second['id']])
        grant.read = True
        grant.save()
        SourceGrant.objects.filter(pk=self.grant_row(self.b).pk).update(read=False)
        self.assertEqual([d['id'] for d in self.listing().data['items']], [first['id']])
        SourceGrant.objects.filter(pk=self.grant_row(self.a).pk).update(read=False)
        with self.assertRaises(DomainError) as caught:
            self.listing()
        self.assertEqual(caught.exception.status, 403)

    def test_summary_query_is_single_pass_without_loading_snapshot_columns(self):
        self.submit('one')
        with CaptureQueriesContext(connection) as queries:
            self.listing()
        selects = [query['sql'] for query in queries if 'FROM "delivery_delivery"' in query['sql']]
        self.assertEqual(len(selects), 1, 'A page must not scan candidates in both resolver and handler.')
        sql = selects[0]
        self.assertIn('JSON_EXTRACT', sql)
        for field in ('workflow_snapshot', 'artifacts_snapshot', 'evidence', 'limitations'):
            self.assertNotIn('"delivery_delivery"."' + field + '"', sql)

    def test_workspace_and_subject_are_both_isolated_for_shared_member(self):
        local = self.submit('local')
        extra_issue = issues.create(self.actor, self.project['id'], 'Another task')
        extra_subject = {'type': 'issue', 'id': str(extra_issue['id'])}
        extra = self.submit('other issue', subject=extra_subject)
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        other_actor = Actor(self.user.pk, self.other.pk)
        project = projects.create(other_actor, 'Other workspace')
        foreign_issue = issues.create(other_actor, project['id'], 'Foreign issue')
        foreign_subject = {'type': 'issue', 'id': str(foreign_issue['id'])}
        foreign = self.act(other_actor, 'delivery.submit', dict(subject=foreign_subject,
                           requirements_revision=1, summary='Foreign result'), key='foreign').data
        self.assertEqual([d['id'] for d in self.listing().data['items']], [local['id']])
        self.assertEqual([d['id'] for d in self.listing(subject=extra_subject).data['items']], [extra['id']])
        self.assertEqual([d['id'] for d in self.listing(other_actor, foreign_subject).data['items']], [foreign['id']])
        for actor, subject in ((self.actor, foreign_subject), (other_actor, self.subject)):
            with self.subTest(subject=subject), self.assertRaises(DomainError) as caught:
                self.listing(actor, subject)
            self.assertEqual(caught.exception.status, 404)

    def test_strict_registry_and_direct_page_inputs_leave_no_audit(self):
        before = self.snapshot()
        invalid = [{'cursor': value} for value in (True, None, '0', -1, MAX_SQLITE_INTEGER)]
        invalid += [{'limit': value} for value in (False, None, '1', 0, 201)]
        invalid += [{'subject': value} for value in ({}, {'type': 'issue', 'id': 1},
                    {'type': 'issue', 'id': '01'}, {'type': 'issue', 'id': '1' * 5000},
                    {'type': 'automation_run', 'id': '1'})]
        invalid += [{'unexpected': 'value'}]
        for extra in invalid:
            payload = dict(subject=self.subject)
            payload.update(extra)
            with self.subTest(payload=repr(payload)[:100]):
                with self.assertRaises(DomainError) as caught:
                    self.act(self.actor, 'delivery.list', payload)
                self.assertEqual(caught.exception.status, 400)
        for field, value in (('cursor', True), ('limit', False), ('cursor', MAX_SQLITE_INTEGER), ('limit', 201)):
            with self.subTest(field=field, value=value):
                with self.assertRaises(DomainError) as caught:
                    service.list_deliveries(self.actor, SubjectRef(**self.subject), **{field: value})
                self.assertEqual(caught.exception.status, 400)
        for subject in (None, SubjectRef('issue', None), SubjectRef('issue', True), SubjectRef('issue', '01')):
            with self.subTest(subject=subject), self.assertRaises(DomainError):
                service.list_deliveries(self.actor, subject)
        self.assertEqual(self.snapshot(), before)

    def test_source_authorization_failure_does_not_masquerade_as_empty_page(self):
        self.submit('one')
        original = service.authorize
        def unavailable(actor, capability, refs):
            original(actor, capability, refs)
            if any(ref.kind == 'delivery' for ref in refs):
                raise DomainError('storage_unavailable', 'Try later.', status=503)
        before = self.snapshot()
        with patch.object(service, 'authorize', unavailable), self.assertRaises(DomainError) as caught:
            self.listing()
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)

    def test_current_membership_and_active_user_are_required_for_all_reads_and_replay(self):
        delivery = self.submit('saved')
        payload = dict(subject=self.subject, requirements_revision=1, summary='saved')
        def rejected():
            before = self.snapshot()
            for action, args, key in (
                ('delivery.read', {'delivery_id': delivery['id']}, None),
                ('delivery.list', {'subject': self.subject}, None),
                ('delivery.submit', payload, 'saved'),
            ):
                with self.subTest(action=action), self.assertRaises(DomainError) as caught:
                    self.act(self.actor, action, args, key=key)
                self.assertIn(caught.exception.status, (403, 404))
            self.assertEqual(self.snapshot(), before)
        self.member.delete()
        rejected()
        self.member = Membership.objects.create(user=self.user, workspace=self.workspace, role='owner')
        self.assertEqual(self.listing().data['items'][0]['id'], delivery['id'])
        self.user.is_active = False
        self.user.save()
        rejected()

    def test_project_rebinding_does_not_rewrite_existing_issue_or_delivery_snapshot(self):
        first = self.submit('first')
        draft = workflows.create(self.actor, 'Published flow')
        version = workflows.publish(self.actor, draft['id'], draft['revision'])
        projects.set_workflow(self.actor, self.project['id'], version['id'], self.project['revision'])
        self.assertEqual(issues.read(self.actor, self.issue['id'])['workflow_snapshot'], self.issue['workflow_snapshot'])
        self.assertEqual(service.read(self.actor, first['id']), first)
        second = self.submit('second')
        self.assertEqual(second['workflow_snapshot'], first['workflow_snapshot'])
        future = issues.create(self.actor, self.project['id'], 'Future task')
        self.assertEqual(future['workflow_snapshot']['version_id'], version['id'])
        self.assertEqual([d['number'] for d in self.listing().data['items']], [1, 2])

    def test_idempotency_save_failure_rolls_back_all_submission_facts_and_retries(self):
        artifact = self.published_artifact()
        before = self.snapshot()
        original = IdempotencyResult.objects.create
        def broken(**kwargs):
            original(**kwargs)
            raise DomainError('storage_unavailable', 'Try later.', status=503)
        with patch.object(IdempotencyResult.objects, 'create', broken), self.assertRaises(DomainError) as caught:
            self.submit('retry', artifact_ids=[artifact['id']])
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        saved = self.submit('retry', artifact_ids=[artifact['id']])
        self.assertEqual(saved['number'], 1)
        self.assertEqual(self.submit('retry', artifact_ids=[artifact['id']]), saved)
        self.assertEqual(Delivery.objects.count(), 1)

    def test_strict_submission_evidence_structure_has_no_partial_records(self):
        artifact = self.published_artifact()
        evidence = dict(criterion_key='documented', artifact_ids=[artifact['id']])
        before = self.snapshot()
        invalid = [dict(artifact_ids=[artifact['id'], artifact['id']]), dict(artifact_ids=None),
                   dict(artifact_ids=[artifact['id']] * 101), dict(evidence=None),
                   dict(evidence=[evidence, evidence]), dict(evidence=[dict(evidence, verified=True)]),
                   dict(evidence=[dict(evidence, artifact_ids=[artifact['id'], artifact['id']])]),
                   dict(evidence=[dict(evidence, note=None)]), dict(evidence=[dict(evidence, note='x' * 4001)]),
                   dict(limitations=None), dict(requirements_revision=True), dict(requirements_revision=MAX_SQLITE_INTEGER),
                   dict(source_refs=None), dict(summary='\ud800')]
        for extra in invalid:
            payload = dict(subject=self.subject, requirements_revision=1, summary='Bad result',
                           artifact_ids=[artifact['id']])
            payload.update(deepcopy(extra))
            with self.subTest(fields=repr(extra)[:100]):
                with self.assertRaises(DomainError) as caught:
                    self.act(self.actor, 'delivery.submit', payload, key='invalid')
                self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.snapshot(), before)
