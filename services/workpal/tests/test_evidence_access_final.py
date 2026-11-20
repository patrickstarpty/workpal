"""Current authorization acceptance through the evidence Interface."""
from unittest.mock import patch
from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from tests import test_evidence_final as fixtures
from workpal.contracts import ActionRequest, DomainError, ObjectRef, Actor
from workpal.actions import registry
from workpal.access.models import RegisteredObject, SourceGrant
from workpal.access.service import register_object, derive_scope
from workpal.audit.models import AuditEvent
from workpal.investigation import evidence
from workpal.investigation.models import Source, Investigation
from workpal.identity.models import Workspace, Membership

class EvidenceAccessFinalTests(TestCase):
    setUp = fixtures.EvidenceFinalTests.setUp
    ready = fixtures.EvidenceFinalTests.ready
    snapshot = fixtures.EvidenceFinalTests.snapshot
    prepare = fixtures.EvidenceFinalTests.prepare
    upload = fixtures.EvidenceFinalTests.upload

    def denied(self, operation, status=None):
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            operation()
        if status is not None:
            self.assertEqual(caught.exception.status, status)
        self.assertEqual(self.snapshot(), before)

    def read_only(self, operation, queries=None):
        before = self.snapshot()
        with CaptureQueriesContext(connection) as captured:
            result = operation()
        if queries is not None:
            queries.extend(captured.captured_queries)
        after = self.snapshot()
        for label, rows in before.items():
            if label == 'audit.AuditEvent':
                self.assertEqual(len(after[label]), len(rows) + 1)
                saved = {row['id']: row for row in after[label]}
                for row in rows:
                    self.assertEqual(saved[row['id']], row)
            else:
                self.assertEqual(after[label], rows, label)
        return result

    def audit(self, action, ids):
        event = AuditEvent.objects.filter(action_id=action).latest('created_at')
        expected = [{'kind': k, 'id': str(i)} for k, i in ids]
        self.assertCountEqual(event.object_refs, expected)
        scope = derive_scope([ObjectRef(x['kind'], x['id']) for x in expected])
        self.assertCountEqual(event.scope_refs, list({(x['kind'], x['id']): x for x in expected + [{'kind': r.kind, 'id': r.id} for r in scope.source_refs]}.values()))
        self.assertNotIn('SECRET-literal', str(event.fields))
        self.assertNotIn('content', event.fields)
        self.assertNotIn('policy', event.fields)

    def test_real_grants_pages_exact_audit_and_projection(self):
        self.prepare()
        rows = [self.row] + [self.upload('page-'+str(i)) for i in range(6)]
        hidden = {rows[i]['id'] for i in (0, 3, 6)}
        for i in (0, 3, 6):
            root = ObjectRef('private-root', str(i))
            register_object(self.actor.workspace_id, root, is_source=True)
            obj = RegisteredObject.objects.get(kind=root.kind, object_id=root.id)
            SourceGrant.objects.create(user_id=self.actor.user_id, source=obj, read=True)
            register_object(self.actor.workspace_id, ObjectRef('evidence', str(rows[i]['id'])), [root])
        self.assertFalse(RegisteredObject.objects.filter(available=False).exists())
        expected = [r for r in rows if r['id'] not in hidden]
        cursor, found, queries = 0, [], []
        while True:
            page = self.read_only(lambda: evidence.list_evidence(self.member, self.investigation, cursor, 2), queries)
            self.audit('evidence.list', [('investigation', self.investigation)] + [('evidence', r['id']) for r in page['items']])
            found += page['items']
            cursor = page['next_cursor']
            if not cursor:
                break
        self.assertEqual(found, expected)
        self.assertEqual(len({r['id'] for r in found}), len(found))
        for query in queries:
            sql = query['sql'].lower()
            if 'select' in sql and 'investigation_evidencesnapshot' in sql:
                self.assertNotIn('"content"', sql)
            if 'select' in sql:
                self.assertNotIn('"policy"', sql)
        self.assertEqual(self.read_only(lambda: evidence.list_evidence(self.member, self.investigation))['items'], expected)
        self.audit('evidence.list', [('investigation', self.investigation)] + [('evidence', r['id']) for r in expected])
        self.assertEqual(self.read_only(lambda: evidence.list_evidence(self.member, self.investigation, rows[-1]['id'])), {'items': [], 'next_cursor': 0})
        self.audit('evidence.list', [('investigation', self.investigation)])
        before = self.snapshot()
        evidence.read_evidence(self.member, expected[0]['id'])
        self.audit('evidence.read', [('evidence', expected[0]['id'])])
        after = self.snapshot()
        for label in before:
            if label != 'audit.AuditEvent':
                self.assertEqual(before[label], after[label], label)

    def test_internal_executor_preserves_user_grants_without_policy_authority(self):
        self.prepare()
        for human in (self.actor, self.member):
            for executor_id in ('', 'runtime-review'):
                with self.subTest(user=human.user_id, executor=executor_id):
                    actor = Actor(human.user_id, human.workspace_id, executor_id)
                    key = 'executor-' + str(human.user_id) + '-' + executor_id
                    row = self.upload(key, actor)
                    self.assertEqual(row['actor_id'], human.user_id)
                    self.assertEqual(self.read_only(lambda: evidence.read_evidence(actor, row['id']))['id'], row['id'])
                    page = self.read_only(lambda: registry.execute(actor, ActionRequest('evidence.list', dict(investigation_id=self.investigation), None, None)).data)
                    self.assertIn(row, page['items'])
                    self.denied(lambda: evidence.read_policy(actor, self.source), 403)
                    revision = Source.objects.get(pk=self.source).policy_revision
                    self.denied(lambda: evidence.configure_policy(actor, self.source, self.policy, revision), 403)
                    payload = dict(investigation_id=self.investigation, source_id=self.source,
                        format=row['format'], raw_sha256=row['raw_sha256'], raw_bytes=row['raw_bytes'],
                        timezone='', range_start='', range_end='')
                    self.denied(lambda: registry.execute(actor, ActionRequest('evidence.upload', payload, None, key)), 403)
                    grants = SourceGrant.objects.filter(user_id=human.user_id, source__kind='environment')
                    self.assertTrue(grants.exists())
                    grants.update(write=False)
                    self.denied(lambda: self.upload(key, actor), 403)
                    self.denied(lambda: self.upload(key+'-new', actor), 403)
                    self.assertEqual(self.read_only(lambda: evidence.read_evidence(actor, row['id']))['id'], row['id'])
                    grants.update(write=True)
                    before = self.snapshot()
                    self.assertEqual(self.upload(key, actor), row)
                    self.assertEqual(self.snapshot(), before)

    def test_authorize_503_is_atomic_and_recovers(self):
        self.prepare()
        original = evidence.authorize
        def fail(actor, action, refs=()):
            original(actor, action, refs)
            if any(r.kind in ('evidence', 'evidence_source') for r in refs):
                raise DomainError('unavailable', 'Unavailable.', status=503)
        for operation in (lambda: evidence.read_evidence(self.member, self.row['id']), lambda: evidence.list_evidence(self.member, self.investigation)):
            with patch.object(evidence, 'authorize', side_effect=fail):
                self.denied(operation, 503)
            self.assertTrue(operation())

    def test_direct_registry_closed_numeric_matrix(self):
        self.prepare()
        for field, values in [('evidence_id', (True, '1', 0, -1, 2**63)), ('investigation_id', (True, '1', 0, -1, 2**63)), ('cursor', (True, '1', -1, 2**63)), ('limit', (True, '1', 0, -1, 201, 2**63))]:
            for value in values:
                payload = {'evidence_id': self.row['id']} if field == 'evidence_id' else {'investigation_id': self.investigation}
                payload[field] = value
                action = 'evidence.read' if field == 'evidence_id' else 'evidence.list'
                self.denied(lambda: registry.execute(self.member, ActionRequest(action, payload, None, None)))
                if field == 'evidence_id': op = lambda: evidence.read_evidence(self.member, value)
                elif field == 'investigation_id': op = lambda: evidence.list_evidence(self.member, value)
                else: op = lambda: evidence.list_evidence(self.member, self.investigation, **{field: value})
                self.denied(op)
        for action, payload in [('evidence.read', {'evidence_id': self.row['id']}), ('evidence.list', {'investigation_id': self.investigation})]:
            self.denied(lambda: registry.execute(self.member, ActionRequest(action, dict(payload, extra=True), None, None)))
        for limit in (1, 200):
            self.assertEqual(evidence.list_evidence(self.member, self.investigation, 0, limit), registry.execute(self.member, ActionRequest('evidence.list', dict(investigation_id=self.investigation, cursor=0, limit=limit), None, None)).data)
        self.assertEqual(evidence.list_evidence(self.member, self.investigation), registry.execute(self.member, ActionRequest('evidence.list', dict(investigation_id=self.investigation), None, None)).data)
        from workpal.investigation.models import EvidenceSnapshot
        saved = EvidenceSnapshot.objects.get(pk=self.row['id'])
        payload = dict(investigation_id=self.investigation, source_id=self.source, format=saved.format, raw_sha256=saved.raw_sha256, raw_bytes=saved.raw_bytes, timezone='', range_start='', range_end='')
        self.denied(lambda: registry.execute(self.member, ActionRequest('evidence.upload', payload, None, 'initial')), 403)
        self.upload('after-invalid', self.member)
        self.assertEqual(evidence.read_evidence(self.member, self.row['id'])['id'], self.row['id'])

    def test_cross_workspace_investigation_and_real_revocation(self):
        self.prepare()
        workspace = Workspace.objects.create(name='second')
        Membership.objects.create(user_id=self.member.user_id, workspace=workspace, role='member')
        other = Actor(self.member.user_id, workspace.pk)
        self.denied(lambda: evidence.read_evidence(other, self.row['id']), 404)
        self.denied(lambda: evidence.submit_upload(other, self.investigation, self.source, b'x', format='text', key='other'), 404)
        source = Source.objects.get(pk=self.source)
        second = registry.execute(self.actor, ActionRequest('investigation.start', dict(project_id=source.environment.project_id, environment_id=source.environment_id, service_id=source.allowed_services.get().pk, problem='Second', key='second'), None, 'second')).data['id']
        old = self.upload('bound', self.member)
        self.denied(lambda: evidence.submit_upload(self.member, second, self.source, b'SECRET-literal final', format='text', key='bound'), 409)
        self.assertEqual(evidence.submit_upload(self.member, second, self.source, b'x', format='text', key='fresh')['investigation_id'], second)
        def create_source(env_id, service_id, key):
            return registry.execute(self.actor, ActionRequest('evidence_source.create_upload', dict(environment_id=env_id, name=key, allowed_services=[service_id]), None, key)).data['id']
        service_id = source.allowed_services.get().pk
        alternate = create_source(source.environment_id, service_id, 'alternate')
        evidence.configure_policy(self.actor, alternate, self.policy, 1)
        self.denied(lambda: evidence.submit_upload(self.member, self.investigation, alternate, b'SECRET-literal final', format='text', key='bound'), 409)
        self.assertEqual(evidence.submit_upload(self.member, self.investigation, alternate, b'x', format='text', key='alternate-new')['source_id'], alternate)
        wrong_service = registry.execute(self.actor, ActionRequest('environment_service.create', dict(environment_id=source.environment_id, name='wrong'), None, 'wrong-service')).data['id']
        mismatch = create_source(source.environment_id, wrong_service, 'mismatch')
        self.denied(lambda: evidence.submit_upload(self.member, self.investigation, mismatch, b'x', format='text', key='bad-service'), 403)
        other_env = registry.execute(self.actor, ActionRequest('environment.create', dict(project_id=source.environment.project_id, name='other-env', timezone='UTC'), None, 'other-env')).data['id']
        other_service = registry.execute(self.actor, ActionRequest('environment_service.create', dict(environment_id=other_env, name='other-service'), None, 'other-service')).data['id']
        wrong_env = create_source(other_env, other_service, 'wrong-env')
        self.denied(lambda: evidence.submit_upload(self.member, self.investigation, wrong_env, b'x', format='text', key='bad-env'), 403)
        membership = Membership.objects.get(user_id=self.member.user_id, workspace_id=self.member.workspace_id)
        membership.delete()
        self.denied(lambda: self.upload('bound', self.member), 404)
        self.denied(lambda: self.upload('membership-new', self.member), 404)
        Membership.objects.create(user_id=self.member.user_id, workspace_id=self.member.workspace_id, role='member')
        for kind in ('environment', 'environment_service', 'evidence_source'):
            obj = RegisteredObject.objects.get(kind=kind, object_id=str({'environment': source.environment_id, 'environment_service': source.allowed_services.get().pk, 'evidence_source': self.source}[kind]))
            obj.is_source = True
            obj.save(update_fields=['is_source'])
            SourceGrant.objects.get_or_create(user_id=self.member.user_id, source=obj, defaults={'read': True, 'write': True})
            grants = SourceGrant.objects.filter(user_id=self.member.user_id, source=obj)
            self.assertTrue(grants.exists())
            grants.update(read=False)
            self.denied(lambda: self.upload('bound', self.member), 403)
            self.denied(lambda: self.upload('new-denied', self.member), 403)
            self.denied(lambda: evidence.read_evidence(self.member, old['id']), 403)
            grants.update(read=True)
        grants = SourceGrant.objects.filter(user_id=self.member.user_id, source__kind='environment')
        grants.update(write=False)
        self.denied(lambda: self.upload('bound', self.member), 403)
        self.denied(lambda: self.upload('new-write', self.member), 403)
        self.assertEqual(evidence.read_evidence(self.member, old['id'])['id'], old['id'])
