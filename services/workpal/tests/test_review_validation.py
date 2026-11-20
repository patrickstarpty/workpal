from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from tests.support import WorkpalCase
from tests.test_delivery_selection_review import SelectionFixtures
from workpal.access.models import SourceGrant
from workpal.access.service import derive_scope
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError, ObjectRef
from workpal.delivery import review, service
from workpal.delivery.models import Artifact, Delivery, DeliveryCurrent, DeliverySelection, Review
from workpal.identity.models import Membership
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work import issues, service as projects
from workpal.work.models import Issue, IssueRequirements
from workpal.workflows import service as workflows
from workpal.workflows.contracts import default_definition


class ReviewFixtures(SelectionFixtures):
    def ready(self):
        artifact = self.published_artifact()
        target = self.submit('target', artifact_ids=[artifact['id']],
            evidence=[dict(criterion_key='documented', artifact_ids=[artifact['id']])])
        self.choose(target, 'chosen', 1)
        return target

    def decide(self, target, key='review', revision=2, outcome='approve', reason='Human review.',
               actor=None, **extra):
        decision = dict(outcome=outcome, reason=reason, **extra)
        return self.act(actor or self.actor, 'delivery.review', dict(delivery_id=target['id'],
            version=target['number'], decision=decision), key=key, revision=revision)


class ReviewValidation(ReviewFixtures, WorkpalCase):
    def test_each_criterion_needs_an_artifact_and_failed_approval_preserves_state(self):
        updated = self.act(self.actor, 'issue.update', dict(issue_id=self.issue['id'], criteria=[
            dict(key='documented', text='A document is supplied.'),
            dict(key='explained', text='The outcome is explained.')]), key='criteria', revision=1).data
        artifact = self.published_artifact()
        payload = dict(subject=self.subject, requirements_revision=updated['requirements_revision'],
            summary='Partial evidence', artifact_ids=[artifact['id']], evidence=[
                dict(criterion_key='documented', artifact_ids=[artifact['id']]),
                dict(criterion_key='explained', artifact_ids=[], note='Claim without an attachment.')])
        partial = self.act(self.actor, 'delivery.submit', payload, key='partial').data
        self.choose(partial, 'partial-choice', 1)
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.decide(partial)
        self.assertEqual(caught.exception.code, 'evidence_required')
        self.assertEqual(self.snapshot(), before)
        payload['evidence'][1]['artifact_ids'] = [artifact['id']]
        complete = self.act(self.actor, 'delivery.submit', payload, key='complete').data
        self.choose(complete, 'complete-choice', 2)
        accepted = self.decide(complete, revision=3).data
        self.assertEqual(accepted['decision']['outcome'], 'approve')
        self.assertEqual(accepted['revision'], 4)
        self.assertFalse({'test_passed', 'exit_code', 'merged'} & set(accepted))

    def test_actual_empty_criteria_submission_can_be_returned_but_not_approved(self):
        task = issues.create(self.actor, self.project['id'], 'No acceptance requirements', criteria=[])
        subject = dict(type='issue', id=str(task['id']))
        target = self.act(self.actor, 'delivery.submit', dict(subject=subject,
            requirements_revision=1, summary='Please clarify'), key='empty').data
        self.choose(target, 'empty-choice', 1)
        with self.assertRaises(DomainError) as caught:
            self.decide(target)
        self.assertEqual(caught.exception.code, 'evidence_required')
        returned = self.decide(target, outcome='request_changes', reason='Define acceptance requirements.').data
        self.assertEqual(returned['requirements_snapshot']['criteria'], [])
        self.assertEqual(returned['decision']['reason'], 'Define acceptance requirements.')

    def test_artifact_metadata_mismatch_is_rejected_before_any_review_write(self):
        target = self.ready()
        artifact = Artifact.objects.select_related('blob').get(pk=target['artifacts_snapshot'][0]['id'])
        digest = artifact.blob.sha256
        artifact.blob.sha256 = '0' * 64
        artifact.blob.save(update_fields=['sha256'])
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.decide(target)
        self.assertEqual(caught.exception.code, 'evidence_conflict')
        self.assertEqual(self.snapshot(), before)
        artifact.blob.sha256 = digest
        artifact.blob.save(update_fields=['sha256'])
        self.assertEqual(self.decide(target).data['delivery_sha256'], target['sha256'])

    def test_changed_requirements_reject_new_approval_without_rewriting_prior_review(self):
        target = self.ready()
        old = self.decide(target).data
        self.act(self.actor, 'issue.update', dict(issue_id=self.issue['id'], title='New requirements'),
                 key='requirements', revision=1)
        before = self.snapshot()
        self.assertEqual(self.decide(target).data, old)
        with self.assertRaises(DomainError) as caught:
            self.decide(target, key='new', revision=3)
        self.assertEqual(caught.exception.code, 'requirements_conflict')
        self.assertEqual(self.snapshot(), before)
        returned = self.decide(target, key='return', revision=3, outcome='request_changes').data
        self.assertEqual(returned['requirements_snapshot'], old['requirements_snapshot'])
        self.assertEqual((returned['revision'], Review.objects.count()), (4, 2))
        self.assertEqual(review.read(self.actor, old['id']), old)

    def test_snapshot_reviewer_roles_apply_without_owner_override_or_project_rebinding(self):
        definition = default_definition()
        definition['review_policy'] = dict(completion='approved_delivery', reviewer_roles=['member'])
        draft = workflows.create(self.actor, 'Member review', definition)
        version = workflows.publish(self.actor, draft['id'], draft['revision'])
        projects.set_workflow(self.actor, self.project['id'], version['id'], 1)
        self.issue = issues.create(self.actor, self.project['id'], 'Custom policy',
            criteria=[dict(key='documented', text='Provide a document.')])
        self.subject = dict(type='issue', id=str(self.issue['id']))
        target = self.ready()
        with self.assertRaises(DomainError) as caught:
            self.decide(target)
        self.assertEqual(caught.exception.status, 403)
        self.member.role = 'member'
        self.member.save()
        saved = self.decide(target).data
        self.member.role = 'owner'
        self.member.save()
        projects.set_workflow(self.actor, self.project['id'], 0, 2)
        with self.assertRaises(DomainError):
            self.decide(target)
        self.assertEqual(review.read(self.actor, saved['id']), saved)
        self.assertEqual(saved['workflow_snapshot']['definition']['review_policy']['reviewer_roles'], ['member'])
        self.member.role = 'member'
        self.member.save()
        self.assertEqual(self.decide(target).data, saved)

    def test_private_review_sources_protect_reason_and_replay_without_restricting_delivery(self):
        target = self.ready()
        private = self.register(self.workspace.pk, ObjectRef('source', 'review-private'), is_source=True)
        grant = self.grant(private, read=True, write=False)
        sources = [dict(kind=private.kind, id=private.id)]
        before = self.snapshot()
        with self.assertRaises(DomainError):
            self.decide(target, source_refs=sources, reason='Restricted reasoning.')
        self.assertEqual(self.snapshot(), before)
        grant.write = True
        grant.save()
        saved = self.decide(target, source_refs=sources, reason='Restricted reasoning.').data
        self.assertEqual(derive_scope([review.ref(saved['id'])]).source_refs, {self.a, self.b, private})
        self.assertEqual(derive_scope([service.ref(target['id'])]).source_refs, {self.a, self.b})
        event = AuditEvent.objects.get(action_id='delivery.review')
        self.assertNotIn('Restricted reasoning.', str(event.fields))
        self.assertIn(dict(kind=private.kind, id=private.id), event.scope_refs)
        self.assertEqual(Outbox.objects.get(event=event).scope_refs, event.scope_refs)
        grant.write = False
        grant.save()
        self.assertEqual(review.read(self.actor, saved['id']), saved)
        with self.assertRaises(DomainError):
            self.decide(target, source_refs=sources, reason='Restricted reasoning.')
        grant.read = False
        grant.save()
        with self.assertRaises(DomainError):
            review.read(self.actor, saved['id'])
        self.assertEqual(self.current().data['current_delivery_id'], target['id'])
        self.assertEqual(service.read(self.actor, target['id']), target)

    def test_shared_workspace_user_and_revoked_membership_cannot_read_or_replay(self):
        target = self.ready()
        saved = self.decide(target).data
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        foreign = Actor(self.user.pk, self.other.pk)
        before = self.snapshot()
        for call in (lambda: self.act(foreign, 'review.read', dict(review_id=saved['id'])),
                     lambda: self.decide(target, actor=foreign)):
            with self.assertRaises(DomainError) as caught: call()
            self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.snapshot(), before)
        self.member.delete()
        for call in (lambda: review.read(self.actor, saved['id']), lambda: self.decide(target)):
            with self.assertRaises(DomainError): call()
        Membership.objects.create(user=self.user, workspace=self.workspace, role='member')
        executor = Actor(self.user.pk, self.workspace.pk, executor_id='read-only-review-reader')
        self.assertEqual(self.act(executor, 'review.read', dict(review_id=saved['id'])).data, saved)
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(DomainError): review.read(self.actor, saved['id'])

    def test_invalid_direct_and_registry_inputs_leave_no_half_decision(self):
        target = self.ready()
        before = self.snapshot()
        good = dict(outcome='approve', reason='Human review.')
        for value in (True, None, '1', 0, -1, MAX_SQLITE_INTEGER):
            for field in ('delivery_id', 'version', 'revision'):
                values = dict(delivery_id=target['id'], version=target['number'], revision=2, decision=good)
                values[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(DomainError) as caught:
                    review.review(self.actor, **values)
                self.assertEqual(caught.exception.status, 400)
        invalid = (None, [], {}, dict(good, verified=True), dict(good, outcome='passed'),
                   dict(good, reason=' '), dict(good, reason='\ud800'), dict(good, source_refs=None),
                   dict(good, source_refs=[dict(kind='x' * 101, id='a')]),
                   dict(good, source_refs=[dict(kind='source', id='\ud800')]))
        for decision in invalid:
            with self.subTest(decision=repr(decision)[:100]):
                with self.assertRaises(DomainError) as caught:
                    review.review(self.actor, target['id'], target['number'], 2, decision)
                self.assertEqual(caught.exception.status, 400)
                with self.assertRaises(DomainError):
                    self.act(self.actor, 'delivery.review', dict(delivery_id=target['id'],
                        version=target['number'], decision=decision), key='invalid', revision=2)
        self.assertEqual(self.snapshot(), before)

    def test_review_catalog_declares_the_same_id_bounds_as_its_interface(self):
        specs = {spec['action_id']: spec for spec in registry.catalog(self.actor)}
        for action, fields in (('delivery.review', ('delivery_id', 'version')), ('review.read', ('review_id',))):
            for field in fields:
                schema = specs[action]['schema']['properties'][field]
                self.assertEqual(schema.get('minimum'), 1)
                self.assertEqual(schema.get('maximum'), MAX_SQLITE_INTEGER - 1)

    def test_review_read_uses_saved_snapshots_without_loading_duplicate_delivery_content(self):
        saved = self.decide(self.ready()).data
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(review.read(self.actor, saved['id']), saved)
        for query in queries:
            for field in ('requirements_snapshot', 'workflow_snapshot', 'artifacts_snapshot', 'evidence'):
                self.assertNotIn('"delivery_delivery"."' + field + '"', query['sql'])

    def test_late_failures_rollback_current_review_sources_audit_and_cache_then_retry(self):
        target = self.ready()
        immutable = {model: list(model.objects.values()) for model in (Issue, IssueRequirements, Delivery, DeliverySelection)}
        for owner, method in ((Review.objects, 'create'), (review, 'register_object'),
                              (registry, 'record'), (IdempotencyResult.objects, 'create')):
            original = getattr(owner, method)
            def broken(*args, **kwargs):
                original(*args, **kwargs)
                raise DomainError('storage_unavailable', 'Retry later.', status=503)
            revision = DeliveryCurrent.objects.get().revision
            key = 'retry-' + str(revision)
            before = self.snapshot()
            with self.subTest(revision=revision), patch.object(owner, method, broken), self.assertRaises(DomainError) as caught:
                self.decide(target, key=key, revision=revision)
            self.assertEqual(caught.exception.status, 503)
            self.assertEqual(self.snapshot(), before)
            saved = self.decide(target, key=key, revision=revision).data
            self.assertEqual(saved['revision'], revision + 1)
            self.assertEqual(self.decide(target, key=key, revision=revision).data, saved)
        for model, rows in immutable.items():
            self.assertEqual(list(model.objects.values()), rows)

    def test_review_derived_rework_and_archive_preserve_original_decision(self):
        target = self.ready()
        old = self.decide(target).data
        artifact = self.published_artifact()
        rework = self.submit('rework', source_refs=[dict(kind='review', id=str(old['id']))],
            artifact_ids=[artifact['id']], evidence=[dict(criterion_key='documented', artifact_ids=[artifact['id']])])
        self.choose(rework, 'rework-choice', 3)
        self.assertEqual(self.decide(target).data, old)
        newer = self.decide(rework, key='rework-review', revision=4).data
        self.assertEqual(newer['revision'], 5)
        self.assertEqual(derive_scope([review.ref(newer['id'])]).source_refs, {self.a, self.b})
        self.act(self.actor, 'issue.archive', dict(issue_id=self.issue['id']), key='archive', revision=1)
        self.assertEqual(review.read(self.actor, old['id']), old)
        self.assertEqual(review.read(self.actor, newer['id']), newer)
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            self.decide(rework, key='after-archive', revision=5)
        self.assertEqual(caught.exception.code, 'issue_archived')
        self.assertEqual(self.snapshot(), before)
