from django.test import TransactionTestCase
from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.execution import service as runs
from workpal.agents import service as agents
from workpal.work import service as projects, issues, resources
from workpal.contracts import DomainError


class FinalAdmission(AccessFixtures, TransactionTestCase):
    act = WorkpalCase.act

    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()
        self.project = projects.create(self.actor, 'Project')
        self.issue = issues.create(self.actor, self.project['id'], 'Task')
        self.agent = agents.create(self.actor, 'Builder')
        self.payload = dict(subject={'type': 'issue', 'id': self.issue['id']},
                            agent_id=self.agent['id'], key='intent')

    def test_new_resource_is_checked_on_direct_replay_and_reuse(self):
        first = runs.start(self.actor, **self.payload)
        grant = self.grant(self.a, read=True, write=True)
        resources.create(self.actor, self.project['id'], 'New restricted repository',
                         'github', 'org/new', source_refs=[{'kind': self.a.kind, 'id': self.a.id}])
        runs.start(self.actor, **self.payload)
        grant.write = False
        grant.save()
        for key in ('intent', 'fresh'):
            for operation in (
                lambda: runs.start(self.actor, **{**self.payload, 'key': key}),
                lambda: self.act(self.actor, 'run.start', {**self.payload, 'key': key}, key=key),
            ):
                with self.assertRaises(DomainError) as error:
                    operation()
                self.assertEqual(error.exception.status, 403)
        self.assertEqual(runs.read(self.actor, first['id'])['input_snapshot'], first['input_snapshot'])

    def snapshot(self, models=None):
        from django.apps import apps
        models = models or [apps.get_model(label) for label in (
            'execution.Run', 'execution.Intent', 'access.RegisteredObject',
            'access.SourceLink', 'actions.IdempotencyResult', 'audit.AuditEvent', 'audit.Outbox')]
        return {m._meta.label: list(m.objects.order_by('pk').values()) for m in models}

    def race(self, operation):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        barrier = Barrier(2)
        def request(index):
            connections['default'].close()
            barrier.wait()
            try:
                return operation(index)
            except DomainError as error:
                return error
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(request, i) for i in range(2)]
            return [future.result() for future in futures]

    def test_two_users_share_run_keep_independent_intents(self):
        from django.contrib.auth import get_user_model
        from workpal.identity.models import Membership
        from workpal.contracts import Actor
        from workpal.execution.models import Run, Intent
        from workpal.audit.models import AuditEvent, Outbox
        from workpal.actions.models import IdempotencyResult
        user = get_user_model().objects.create(username='second')
        Membership.objects.create(user=user, workspace=self.workspace, role='owner')
        actors = [self.actor, Actor(user.pk, self.workspace.pk)]
        results = self.race(lambda i: self.act(actors[i], 'run.start', self.payload, key='shared').data)
        self.assertTrue(all(isinstance(r, dict) for r in results), results)
        self.assertEqual(results[0]['id'], results[1]['id'])
        self.assertEqual(Run.objects.count(), 1)
        self.assertEqual(Intent.objects.count(), 2)
        for actor in actors:
            self.assertEqual(Intent.objects.filter(actor_id=actor.user_id).count(), 1)
            self.assertEqual(AuditEvent.objects.filter(actor_id=actor.user_id, action_id='run.start').count(), 1)
            self.assertEqual(Outbox.objects.filter(event__actor_id=actor.user_id, action_id='run.start').count(), 1)
            self.assertEqual(IdempotencyResult.objects.filter(user_id=actor.user_id, action_id='run.start').count(), 1)
        before = self.snapshot()
        for actor in actors:
            self.act(actor, 'run.start', self.payload, key='shared')
        self.assertEqual(self.snapshot(), before)

    def test_agent_and_requirements_revocation(self):
        for target in ('agent', 'requirements'):
            for permission in ('read', 'write'):
                with self.subTest(target=target, permission=permission):
                    source = self.a if target == 'agent' else self.b
                    from workpal.access.models import SourceGrant, RegisteredObject
                    grant, _ = SourceGrant.objects.update_or_create(user=self.user, source=RegisteredObject.objects.get(kind=source.kind, object_id=source.id), defaults={'read': True, 'write': True})
                    ref = agents.ref(self.agent['id']) if target == 'agent' else issues.requirement_ref(self.issue['requirements_version_id'])
                    self.register(self.workspace.pk, ref, [source])
                    payload = {**self.payload, 'key': target + permission}
                    first = runs.start(self.actor, **payload)
                    self.act(self.actor, 'run.start', payload, key=payload['key'])
                    self.assertEqual(runs.read(self.actor, first['id'])['id'], first['id'])
                    self.act(self.actor, 'run.read', {'run_id': first['id']})
                    setattr(grant, permission, False)
                    grant.save()
                    before = self.snapshot()
                    for key in (payload['key'], payload['key'] + '-new'):
                        for operation in (
                            lambda: runs.start(self.actor, **{**payload, 'key': key}),
                            lambda: self.act(self.actor, 'run.start', {**payload, 'key': key}, key=key),
                            lambda: runs.control(self.actor, first['id'], 'cancel', 1),
                            lambda: self.act(self.actor, 'run.cancel', {'run_id': first['id']}, key=key, revision=1),
                        ):
                            with self.assertRaises(DomainError) as error:
                                operation()
                            self.assertEqual(error.exception.status, 403)
                    self.assertEqual(self.snapshot(), before)
                    for operation in (lambda: runs.read(self.actor, first['id']), lambda: self.act(self.actor, 'run.read', {'run_id': first['id']})):
                        if permission == 'write':
                            operation()
                        else:
                            with self.assertRaises(DomainError) as error:
                                operation()
                            self.assertEqual(error.exception.status, 403)
                    grant.read = grant.write = True
                    grant.save()

    def test_cancel_revision_race(self):
        from workpal.audit.models import AuditEvent, Outbox
        first = runs.start(self.actor, **self.payload)
        issue = issues.read(self.actor, self.issue['id'])
        results = self.race(lambda i: self.act(self.actor, 'run.cancel', {'run_id': first['id']}, key='cancel-' + str(i), revision=1))
        failures = [r for r in results if isinstance(r, DomainError)]
        self.assertEqual(len(failures), 1, results)
        self.assertEqual((failures[0].status, failures[0].code), (409, 'revision_conflict'))
        self.assertEqual(AuditEvent.objects.filter(action_id='run.cancel').count(), 1)
        self.assertEqual(Outbox.objects.filter(action_id='run.cancel').count(), 1)
        self.assertEqual(runs.read(self.actor, first['id'])['revision'], 2)
        self.assertEqual(issues.read(self.actor, self.issue['id']), issue)

    def test_actual_audit_failure_rolls_back(self):
        from unittest.mock import patch
        from workpal.actions import registry
        from workpal.audit.models import AuditEvent, Outbox
        before = self.snapshot()
        original = registry.record
        observed = []
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            observed.append((AuditEvent.objects.filter(action_id='run.start').count(), Outbox.objects.filter(action_id='run.start').count()))
            raise DomainError('audit_unavailable', 'Unavailable', status=503)
        with patch.object(registry, 'record', side_effect=fail):
            with self.assertRaises(DomainError) as error:
                self.act(self.actor, 'run.start', self.payload, key='rollback')
        self.assertEqual(error.exception.status, 503)
        self.assertEqual(observed, [(1, 1)])
        self.assertEqual(self.snapshot(), before)
        self.act(self.actor, 'run.start', self.payload, key='rollback')
        after = self.snapshot()
        self.act(self.actor, 'run.start', self.payload, key='rollback')
        self.assertEqual(self.snapshot(), after)
        for label in ('execution.Run', 'execution.Intent', 'actions.IdempotencyResult', 'audit.AuditEvent', 'audit.Outbox'):
            self.assertEqual(len(after[label]) - len(before[label]), 1, label)

    def test_cross_workspace_and_read_effects(self):
        from workpal.identity.models import Membership
        from workpal.contracts import Actor
        from workpal.audit.models import AuditEvent
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        other = Actor(self.user.pk, self.other.pk)
        project = projects.create(other, 'Other')
        issue = issues.create(other, project['id'], 'Other')
        agent = agents.create(other, 'Other')
        first = runs.start(self.actor, **self.payload)
        before = self.snapshot()
        for operation in (
            lambda: runs.read(other, first['id']),
            lambda: self.act(other, 'run.read', {'run_id': first['id']}),
            lambda: runs.start(self.actor, **{**self.payload, 'agent_id': agent['id']}),
            lambda: self.act(self.actor, 'run.start', {**self.payload, 'agent_id': agent['id']}, key='cross-agent'),
            lambda: runs.start(self.actor, **{**self.payload, 'subject': {'type': 'issue', 'id': issue['id']}}),
            lambda: self.act(self.actor, 'run.start', {**self.payload, 'subject': {'type': 'issue', 'id': issue['id']}}, key='cross-issue'),
        ):
            with self.assertRaises(DomainError):
                operation()
            self.assertEqual(self.snapshot(), before)
        self.assertEqual(runs.read(self.actor, first['id']), first)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.act(self.actor, 'run.read', {'run_id': first['id']}).data, first)
        after = self.snapshot()
        audit = after.pop('audit.AuditEvent')
        prior = before.pop('audit.AuditEvent')
        self.assertEqual(after, before)
        self.assertEqual(len(audit), len(prior) + 1)
        event = AuditEvent.objects.get(action_id='run.read')
        self.assertEqual((event.workspace_id, event.actor_id), (self.workspace.pk, self.user.pk))
        self.assertIn({'kind': 'run', 'id': str(first['id'])}, event.object_refs)
