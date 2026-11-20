import re
from dataclasses import asdict
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from tests.support import WorkpalCase
from tests.test_review_validation import ReviewFixtures
from workpal.access.models import SourceGrant
from workpal.actions import registry
from workpal.audit.models import AuditEvent
from workpal.contracts import Actor, DomainError, ObjectRef, SubjectRef
from workpal.delivery import approval, review, service
from workpal.delivery.models import Review
from workpal.identity.models import Membership
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work import issues, service as projects
from workpal.workflows import service as workflows
from workpal.workflows.contracts import default_definition


class ApprovalReview(ReviewFixtures, WorkpalCase):
    def inspect(self, actor=None, subject=None):
        return self.act(actor or self.actor, 'delivery.approval.read',
                        dict(subject=subject or self.subject))

    def test_latest_private_decision_never_falls_back_to_public_approval(self):
        target = self.ready()
        old = self.decide(target).data
        private = self.register(self.workspace.pk, ObjectRef('source', 'private-review'), is_source=True)
        grant = self.grant(private, read=True, write=True)
        latest = self.decide(target, key='private-return', revision=3, outcome='request_changes',
            reason='Restricted decision.', source_refs=[asdict(private)]).data
        grant.read = False
        grant.save()
        self.assertEqual(review.read(self.actor, old['id']), old)
        self.assertEqual(self.current().data['current_delivery_id'], target['id'])
        before = self.snapshot()
        for call in (self.inspect, lambda: approval.inspect(self.actor, SubjectRef(**self.subject))):
            with self.assertRaises(DomainError) as caught:
                call()
            self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
        grant.read, grant.write = True, False
        grant.save()
        self.member.role = 'member'
        self.member.save()
        executor = Actor(self.user.pk, self.workspace.pk, executor_id='reader')
        result = self.inspect(executor)
        self.assertEqual((result.data['status'], result.data['reason'], result.data['review_id']),
                         ('not_approved', 'changes_requested', latest['id']))
        expected = {issues.ref(self.issue['id']), issues.requirement_ref(self.issue['requirements_version_id']),
                    service.ref(target['id']), review.ref(latest['id'])}
        self.assertEqual(set(result.object_refs), expected)
        event = AuditEvent.objects.filter(action_id='delivery.approval.read').get()
        self.assertEqual(event.fields, dict(subject=self.subject))
        self.assertEqual({ObjectRef(**ref) for ref in event.scope_refs}, expected | {self.a, self.b, private})
        self.assertNotIn('Restricted decision.', str(event.fields))

    def test_current_requirements_have_their_own_authorization_even_for_stale_delivery(self):
        target = self.ready()
        self.decide(target)
        changed = issues.update(self.actor, self.issue['id'], 1, title='New requirement')
        private = self.register(self.workspace.pk, ObjectRef('source', 'new-requirement'), is_source=True)
        self.register(self.workspace.pk, issues.requirement_ref(changed['requirements_version_id']), [private])
        # The approved old Delivery does not inherit the new requirement.
        self.assertEqual(service.read(self.actor, target['id']), target)
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.inspect()
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)
        self.grant(private, read=True, write=False)
        result = self.inspect()
        self.assertEqual((result.data['reason'], result.data['requirements_revision']),
                         ('requirements_changed', 2))
        self.assertIn(issues.requirement_ref(changed['requirements_version_id']), result.object_refs)
        event = AuditEvent.objects.filter(action_id='delivery.approval.read').get()
        self.assertIn(asdict(private), event.scope_refs)

    def test_restoring_the_same_requirement_text_does_not_restore_old_approval(self):
        target = self.ready()
        saved = self.decide(target).data
        issues.update(self.actor, self.issue['id'], 1, title='Temporary change')
        restored = issues.update(self.actor, self.issue['id'], 2, title=self.issue['title'])
        current = issues.read_requirements(self.actor, self.issue['id'], 3)
        self.assertEqual(current['sha256'], saved['requirements_snapshot']['sha256'])
        self.assertNotEqual(current['id'], saved['requirements_snapshot']['id'])
        result = self.inspect().data
        self.assertEqual((result['status'], result['reason'], result['review_id'], result['requirements_revision']),
                         ('not_approved', 'requirements_changed', saved['id'], restored['requirements_revision']))
        self.assertEqual(review.read(self.actor, saved['id']), saved)

    def test_issue_policy_is_its_own_snapshot_after_project_rebinding(self):
        definition = default_definition()
        definition['review_policy']['completion'] = 'approved_delivery'
        draft = workflows.create(self.actor, 'Document review', definition)
        version = workflows.publish(self.actor, draft['id'], draft['revision'])
        projects.set_workflow(self.actor, self.project['id'], version['id'], 1)
        self.issue = issues.create(self.actor, self.project['id'], 'Document',
            criteria=[dict(key='documented', text='Provide a document.')])
        self.subject = dict(type='issue', id=str(self.issue['id']))
        self.decide(self.ready())
        projects.set_workflow(self.actor, self.project['id'], 0, 2)
        result = self.inspect().data
        self.assertEqual((result['status'], result['completion_policy']), ('approved', 'approved_delivery'))
        self.assertEqual(issues.read(self.actor, self.issue['id'])['status_key'], 'backlog')
        self.assertFalse({'can_complete', 'tests_passed', 'merged'} & set(result))

    def test_private_unselected_candidates_do_not_affect_current_approval(self):
        private = self.register(self.workspace.pk, ObjectRef('source', 'candidate'), is_source=True)
        grant = self.grant(private, read=True, write=True)
        self.submit('unselected', source_refs=[asdict(private)])
        grant.read = False
        grant.save()
        empty = self.inspect()
        self.assertEqual((empty.data['reason'], empty.data['current_revision']), ('no_current_delivery', 1))
        self.assertEqual(set(empty.object_refs), {issues.ref(self.issue['id']),
                         issues.requirement_ref(self.issue['requirements_version_id'])})
        target = self.ready()
        saved = self.decide(target).data
        grant.read = True
        grant.save()
        newer = self.submit('newer-unselected', source_refs=[asdict(private)])
        grant.read = False
        grant.save()
        result = self.inspect().data
        self.assertGreater(newer['number'], target['number'])
        self.assertEqual((result['status'], result['current_delivery_id'], result['review_id']),
                         ('approved', target['id'], saved['id']))

    def test_read_currently_requires_each_source_membership_and_workspace(self):
        self.decide(self.ready())
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        foreign = Actor(self.user.pk, self.other.pk)
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.inspect(foreign)
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.snapshot(), before)
        for source in (self.a, self.b):
            grant = SourceGrant.objects.get(user=self.user, source__kind=source.kind, source__object_id=source.id)
            grant.read = False
            grant.save()
            before = self.snapshot()
            with self.assertRaises(DomainError) as caught:
                self.inspect()
            self.assertEqual(caught.exception.status, 403)
            self.assertEqual(self.snapshot(), before)
            grant.read = True
            grant.save()
        self.member.delete()
        with self.assertRaises(DomainError):
            self.inspect()
        Membership.objects.create(user=self.user, workspace=self.workspace, role='member')
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(DomainError):
            self.inspect()

    def test_success_writes_only_access_audit_and_failures_roll_back_actual_audit(self):
        saved = self.decide(self.ready()).data
        before = self.snapshot()
        data, refs = approval.inspect(self.actor, SubjectRef(**self.subject))
        self.assertEqual(data['status'], 'approved')
        self.assertEqual(self.snapshot(), before)
        original_authorize = approval.authorize
        def unavailable(actor, capability, objects):
            original_authorize(actor, capability, objects)
            if review.ref(saved['id']) in objects:
                raise DomainError('storage_unavailable', 'Retry later.', status=503)
        with patch.object(approval, 'authorize', unavailable), self.assertRaises(DomainError) as caught:
            self.inspect()
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        original_record = registry.record
        def fail_after_record(*args, **kwargs):
            original_record(*args, **kwargs)
            self.assertEqual(AuditEvent.objects.filter(action_id='delivery.approval.read').count(), 1)
            raise DomainError('storage_unavailable', 'Retry later.', status=503)
        with patch.object(registry, 'record', fail_after_record), self.assertRaises(DomainError) as caught:
            self.inspect()
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        result = self.inspect()
        self.assertEqual(result.data, data)
        self.assertEqual(result.object_refs, refs)
        after = self.snapshot()
        self.assertEqual(len(after['audit.AuditEvent']), len(before['audit.AuditEvent']) + 1)
        before.pop('audit.AuditEvent')
        after.pop('audit.AuditEvent')
        self.assertEqual(after, before)

    def test_metadata_queries_never_load_large_snapshots_or_evidence_bytes(self):
        self.decide(self.ready())
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.inspect().data['status'], 'approved')
        for table in ('delivery_delivery', 'delivery_review'):
            selections = [q['sql'] for q in queries if 'FROM "' + table + '"' in q['sql']]
            self.assertEqual(len(selections), 1)
            sql = selections[0]
            self.assertIn('JSON_EXTRACT', sql)
            for column in ('requirements_snapshot', 'workflow_snapshot'):
                self.assertIsNone(re.search(r'(?:SELECT |, )"' + table + r'"\."' + column + r'"(?:,| FROM)', sql))
        for query in queries:
            for table in ('delivery_artifact', 'delivery_artifactblob', 'delivery_uploadchunk'):
                self.assertNotIn('FROM "' + table + '"', query['sql'])

    def test_strict_subjects_and_closed_bounded_output_contract(self):
        before = self.snapshot()
        for subject in (None, {}, [], dict(type='issue', id=True), dict(type='issue', id='01'),
                        dict(type='issue', id=str(MAX_SQLITE_INTEGER)), dict(type='conversation', id='1'),
                        dict(self.subject, workspace_id=self.other.pk)):
            with self.subTest(subject=subject), self.assertRaises(DomainError) as caught:
                self.act(self.actor, 'delivery.approval.read', dict(subject=subject))
            self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.snapshot(), before)
        spec = next(s for s in registry.catalog(self.actor) if s['action_id'] == 'delivery.approval.read')
        self.assertFalse(spec['mutating'])
        schema = spec['output_schema']
        self.assertFalse(schema['additionalProperties'])
        properties = schema['properties']
        self.assertEqual(set(properties['completion_policy'].get('enum', [])),
                         {'manual', 'approved_delivery', 'approved_head_merged'})
        for name in ('current_revision', 'requirements_revision', 'current_delivery_id',
                     'current_delivery_number', 'review_id', 'review_revision'):
            self.assertEqual(properties[name]['minimum'], 1 if name in ('current_revision', 'requirements_revision') else 0)
            self.assertEqual(properties[name].get('maximum'), MAX_SQLITE_INTEGER)

    def test_inconsistent_saved_decision_never_counts_as_current_approval(self):
        saved = self.decide(self.ready()).data
        row = Review.objects.get(pk=saved['id'])
        # Deliberate persistence fault injection, not a supported business edit.
        for field, invalid in (('version', row.version + 1), ('delivery_sha256', '0' * 64),
                               ('outcome', 'unknown'), ('workflow_snapshot', dict(row.workflow_snapshot, sha256='0' * 64))):
            original = getattr(row, field)
            setattr(row, field, invalid)
            row.save(update_fields=[field])
            result = self.inspect().data
            self.assertEqual((result['status'], result['reason']), ('not_approved', 'submission_changed'))
            setattr(row, field, original)
            row.save(update_fields=[field])
