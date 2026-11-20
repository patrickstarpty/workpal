"""Additional public management Interface permission and secrecy checks."""
from copy import deepcopy
from django.test import TestCase
from django.contrib.auth import get_user_model
from tests import test_query_configuration as fixtures
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.actions.registry import execute
from workpal.identity.models import Membership, Workspace
from workpal.access.models import SourceGrant
from workpal.investigation import query_config
from workpal.actions.models import Confirmation


class QueryConfigurationPermissionsTests(TestCase):
    setUp = fixtures.QueryConfigurationTests.setUp
    snapshot = fixtures.QueryConfigurationTests.snapshot
    confirmed = fixtures.QueryConfigurationTests.confirmed
    configure = fixtures.QueryConfigurationTests.configure

    def denied(self, call, status=None):
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            call()
        if status is not None:
            self.assertEqual(caught.exception.status, status)
        self.assertEqual(before, self.snapshot())
        return caught.exception

    def test_roles_executor_and_membership_lifecycle(self):
        member = Membership.objects.get(user_id=self.actor.user_id)
        for role in ('owner', 'admin'):
            member.role = role; member.save()
            self.assertFalse(query_config.read_config(self.actor, self.source)['connected'])
            self.assertFalse(execute(self.actor, ActionRequest('query_config.read', dict(source_id=self.source), None, None)).data['connected'])
        request = self.configure()
        member.role = 'member'; member.save()
        for actor in (self.actor, Actor(self.actor.user_id, self.actor.workspace_id, executor_id='machine')):
            self.denied(lambda: query_config.read_config(actor, self.source), 403)
            self.denied(lambda: execute(actor, request), 403)
        member.role = 'admin'; member.save()
        machine = Actor(self.actor.user_id, self.actor.workspace_id, executor_id='machine')
        self.denied(lambda: query_config.read_config(machine, self.source), 403)
        self.denied(lambda: execute(machine, request), 403)
        user = get_user_model().objects.get(pk=self.actor.user_id)
        user.is_active = False; user.save()
        self.denied(lambda: execute(self.actor, request))
        self.denied(lambda: query_config.read_config(self.actor, self.source))
        user.is_active = True; user.save()
        member.delete()
        self.denied(lambda: execute(self.actor, request))
        self.denied(lambda: query_config.read_config(self.actor, self.source))
        Membership.objects.create(user=user, workspace_id=self.actor.workspace_id, role='owner')
        execute(self.actor, request)

    def test_confirmation_actor_workspace_and_action_binding(self):
        request = self.configure()
        user = get_user_model().objects.create(username='second-manager')
        Membership.objects.create(user=user, workspace_id=self.actor.workspace_id, role='admin')
        for grant in SourceGrant.objects.filter(user_id=self.actor.user_id):
            SourceGrant.objects.create(user=user, source=grant.source, read=grant.read, write=grant.write, publish=grant.publish)
        other = Actor(user.pk, self.actor.workspace_id)
        self.assertFalse(query_config.read_config(other, self.source)['connected'])
        self.assertEqual(self.denied(lambda: execute(other, request), 409).code, 'confirmation_conflict')
        original_actor = self.actor
        original_source = self.source
        workspace = Workspace.objects.create(name='target-workspace')
        Membership.objects.create(user_id=original_actor.user_id, workspace=workspace, role='owner')
        target_actor = Actor(original_actor.user_id, workspace.pk)
        def call(action, payload, key):
            return execute(target_actor, ActionRequest(action, payload, None, key)).data['id']
        project = call('project.create', dict(name='target'), 'target-p')
        environment = call('environment.create', dict(project_id=project, name='target', timezone='UTC'), 'target-e')
        service = call('environment_service.create', dict(environment_id=environment, name='target'), 'target-s')
        target_source = call('evidence_source.create_query', dict(environment_id=environment, name='target', allowed_services=[service]), 'target-src')
        # Same user has full normal target access before using a foreign workspace token.
        query_config.configure_policy(target_actor, target_source, self.policy, 1)
        foreign = deepcopy(request); foreign.payload['source_id'] = target_source
        self.assertFalse(query_config.read_config(target_actor, target_source)['connected'])
        self.assertEqual(self.denied(lambda: execute(target_actor, foreign), 409).code, 'confirmation_conflict')
        self.denied(lambda: query_config.read_config(original_actor, target_source), 404)
        self.actor, self.source = original_actor, original_source
        policy_request = self.confirmed('query_policy.configure', dict(policy=self.policy), 'cross-policy', 2)
        for original, action, payload, revision in (
            (request, 'query_policy.configure', dict(policy=self.policy), 2),
            (policy_request, 'query_config.configure', dict(config=self.config), 1),
        ):
            changed = deepcopy(original); changed.action_id = action
            changed.payload = dict(source_id=self.source, **payload); changed.expected_revision = revision
            self.assertEqual(self.denied(lambda: execute(self.actor, changed), 409).code, 'confirmation_conflict')

    def test_independent_upstream_grants_waiting_and_completed(self):
        from workpal.access.models import RegisteredObject
        from workpal.investigation.models import Source
        source = Source.objects.get(pk=self.source)
        objects = [RegisteredObject.objects.get(kind='environment', object_id=str(source.environment_id)),
                   RegisteredObject.objects.get(kind='environment_service', object_id=str(source.allowed_services.first().pk)),
                   RegisteredObject.objects.get(kind='evidence_source', object_id=str(source.pk))]
        for obj in objects:
            obj.is_source = True; obj.save()
            SourceGrant.objects.get_or_create(user_id=self.actor.user_id, source=obj, defaults=dict(read=True, write=True, publish=True))
        grants = list(SourceGrant.objects.filter(user_id=self.actor.user_id, source__in=objects).select_related('source'))
        self.assertEqual(len(grants), 3)
        request = self.configure()
        for completed in (False, True):
            if completed:
                execute(self.actor, request)
            for grant in grants:
                for capability in ('read', 'write', 'publish'):
                    with self.subTest(completed=completed, source=grant.source.kind, capability=capability):
                        setattr(grant, capability, False); grant.save()
                        required = capability in ('read', 'publish') or (capability == 'write' and grant.source.kind == 'environment')
                        if required:
                            self.denied(lambda: query_config.read_config(self.actor, self.source))
                            self.denied(lambda: execute(self.actor, request))
                            self.assertEqual(Confirmation.objects.get(pk=request.confirmation_id).consumed, completed)
                        else:
                            self.assertFalse(query_config.read_config(self.actor, self.source)['connected'])
                        setattr(grant, capability, True); grant.save()
                        self.assertFalse(query_config.read_config(self.actor, self.source)['connected'])
            if not completed:
                self.assertFalse(Confirmation.objects.get(pk=request.confirmation_id).consumed)
        before = self.snapshot(); execute(self.actor, request)
        self.assertEqual(before, self.snapshot())

    def test_legal_length_limits_and_adjacent_rejections(self):
        query_config.configure_policy(self.actor, self.source, self.policy, 1)
        revision = 1
        for field, maximum in (('endpoint', 2048), ('secret_ref', 200), ('reference', 1000), ('attestation', 2000)):
            config = deepcopy(self.config)
            value = 'x' * maximum
            if field == 'endpoint':
                prefix = 'https://limits.example/'
                value = prefix + 'x' * (maximum-len(prefix))
            target = config['readonly_proof'] if field in ('reference', 'attestation') else config
            target[field] = value
            result = query_config.configure(self.actor, self.source, config, revision)
            revision = result['revision']
            request = self.confirmed('query_config.configure', dict(config=config), 'limit-'+field, revision)
            revision = execute(self.actor, request).data['revision']
            target[field] += 'x'
            for registry in (False, True):
                call = (lambda: execute(self.actor, ActionRequest('query_config.configure', dict(source_id=self.source, config=config), revision, 'bad-'+field))) if registry else (lambda: query_config.configure(self.actor, self.source, config, revision))
                self.assertEqual(self.denied(call, 400).code, 'invalid_input')

    def test_safe_projection_and_persistent_record_secrecy(self):
        from django.apps import apps
        import logging
        from unittest.mock import patch
        markers = ['unique-endpoint-marker', 'unique-secret-marker', 'unique-proof-marker', 'unique-policy-marker']
        self.config['endpoint'] = 'https://unique-endpoint-marker.example/search'
        self.config['secret_ref'] = markers[1]
        self.config['readonly_proof']['reference'] = markers[2]
        self.config['readonly_proof']['attestation'] = markers[2]
        self.policy['redact_literals'] = [markers[3]]
        with patch.object(logging.Logger, '_log') as captured:
            request = self.configure(); execute(self.actor, request)
            direct = query_config.read_config(self.actor, self.source)
            registry = execute(self.actor, ActionRequest('query_config.read', dict(source_id=self.source), None, None)).data
            self.assertEqual(direct, registry)
            self.assertEqual(set(direct), {'source_id', 'revision', 'config_sha256', 'configured', 'connected'})
            self.assertFalse(direct['connected'])
            invalid = deepcopy(self.config); invalid['extra'] = markers
            error = self.denied(lambda: query_config.configure(self.actor, self.source, invalid, 2), 400)
        surfaces = str(direct) + str(error) + str(captured.call_args_list)
        for label in ('actions.Confirmation', 'actions.IdempotencyResult', 'audit.AuditEvent', 'audit.Outbox'):
            surfaces += str(list(apps.get_model(label).objects.values()))
        for marker in markers:
            self.assertNotIn(marker, surfaces)
        self.assertEqual(query_config.read_policy(self.actor, self.source)['policy'], self.policy)
