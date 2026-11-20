"""Independent public-Interface checks; no inherited test methods."""
import copy
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from workpal.identity.models import Membership, Workspace
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.actions import registry
from workpal.workflows import persistence as p
from workpal.workflows.graph_models import GraphDraft, GraphVersion
from workpal.access.models import RegisteredObject, SourceLink
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.storage import MAX_SQLITE_INTEGER


class GraphPersistenceIndependentReview(TestCase):
    def setUp(self):
        user = get_user_model().objects.create(username='independent-review')
        workspace = Workspace.objects.create(name='Independent review')
        Membership.objects.create(user=user, workspace=workspace, role='owner')
        self.actor = Actor(user.pk, workspace.pk)
        self.definition = dict(nodes=[dict(id='start', type='start', config={}),
            dict(id='end', type='end', config={})], edges=[dict(
                **{'from': 'start', 'to': 'end'}, on='always', required=True,
                max_traversals=0)], declared_fields=[])

    def snapshot(self):
        return {model._meta.label: list(model.objects.order_by('pk').values())
                for model in (GraphDraft, GraphVersion, RegisteredObject,
                              SourceLink, IdempotencyResult, AuditEvent, Outbox)}

    def test_full_rows_rollback_after_real_record_and_same_key_retry(self):
        for action in ('create', 'update', 'publish'):
            with self.subTest(action=action):
                draft = p.create(self.actor, 'Original', self.definition)
                payload = dict(name='Changed', definition=copy.deepcopy(self.definition))
                revision = None
                if action != 'create':
                    payload['draft_id'] = draft['id']
                    revision = draft['revision']
                if action == 'publish':
                    payload = dict(draft_id=draft['id'])
                request = ActionRequest('workflow_graph.' + action, payload,
                                        revision, 'rollback-' + action)
                before = self.snapshot()
                original = registry.record
                def fail(*args, **kwargs):
                    original(*args, **kwargs)
                    raise DomainError('storage_busy', 'Injected after record', status=503)
                with patch.object(registry, 'record', side_effect=fail):
                    with self.assertRaises(DomainError) as caught:
                        registry.execute(self.actor, request)
                self.assertEqual(caught.exception.status, 503)
                self.assertEqual(self.snapshot(), before)
                result = registry.execute(self.actor, request)
                after = self.snapshot()
                self.assertEqual(registry.execute(self.actor, request).data, result.data)
                self.assertEqual(self.snapshot(), after)

    def test_strict_direct_ids_revisions_and_no_partial_changes(self):
        draft = p.create(self.actor, 'Original', self.definition)
        for value in (True, False, '1', 0, -1, MAX_SQLITE_INTEGER + 1):
            with self.subTest(value=value):
                before = self.snapshot()
                for operation in (lambda: p.read(self.actor, value),
                                  lambda: p.read_version(self.actor, value),
                                  lambda: p.update(self.actor, draft['id'], value, 'Changed', self.definition),
                                  lambda: p.publish(self.actor, draft['id'], value)):
                    with self.assertRaises(DomainError):
                        operation()
                self.assertEqual(self.snapshot(), before)
        before = self.snapshot()
        with self.assertRaises(DomainError):
            p.publish(self.actor, draft['id'], MAX_SQLITE_INTEGER)
        self.assertEqual(self.snapshot(), before)

    def test_pagination_propagates_503(self):
        p.create(self.actor, 'Visible', self.definition)
        before = self.snapshot()
        with patch.object(p.access, 'authorize', side_effect=DomainError(
                'storage_busy', 'Unavailable', status=503)):
            with self.assertRaises(DomainError) as caught:
                p.list_drafts(self.actor)
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
