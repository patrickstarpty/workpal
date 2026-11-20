from django import forms
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.actions import schemas
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import Outbox
from workpal.contracts import DomainError
from workpal.work import resource_actions


class ResourceReviewTests(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()
        self.project = self.act(self.actor, 'project.create', {'name': 'Project'}, key='p').data
        self.payload = dict(project_id=self.project['id'], label='Repository',
                            provider='github', repository_ref='org/repository')

    def test_create_schema_keeps_required_fields_after_update_form_is_defined(self):
        self.assertEqual(set(schemas.form_schema(resource_actions.Create)['required']),
                         {'project_id', 'label', 'provider', 'repository_ref'})
        self.assertEqual(set(schemas.form_schema(resource_actions.Update)['required']),
                         {'project_id', 'resource_id'})

    def test_source_cycle_rolls_back_resource_update_and_registration(self):
        from workpal.access.models import SourceLink
        resource = self.act(self.actor, 'resource.create', self.payload, key='r').data
        before = SourceLink.objects.count()
        with self.assertRaises(DomainError):
            self.act(self.actor, 'resource.update',
                     dict(project_id=self.project['id'], resource_id=resource['id'], label='must roll back',
                          source_refs=[{'kind': 'project_resource', 'id': str(resource['id'])}]),
                     key='cycle', revision=1)
        current = self.act(self.actor, 'resource.read',
                           dict(project_id=self.project['id'], resource_id=resource['id'])).data
        self.assertEqual(current, resource)
        self.assertEqual(SourceLink.objects.count(), before)
        self.assertFalse(IdempotencyResult.objects.filter(key='cycle').exists())
        self.assertFalse(Outbox.objects.filter(action_id='resource.update').exists())

    def test_visible_pagination_skips_resource_after_one_source_is_revoked(self):
        from workpal.access.service import derive_scope
        from workpal.contracts import ObjectRef
        self.grant(self.a, read=True, write=True)
        second_grant = self.grant(self.b, read=True, write=True)
        payload = dict(self.payload, source_refs=[{'kind': r.kind, 'id': r.id} for r in (self.a, self.b)])
        hidden = self.act(self.actor, 'resource.create', payload, key='restricted').data
        first = self.act(self.actor, 'resource.create', self.payload, key='first').data
        last = self.act(self.actor, 'resource.create', self.payload, key='last').data
        self.act(self.actor, 'resource.update',
                 dict(project_id=self.project['id'], resource_id=hidden['id'], source_refs=[]),
                 key='no-removal', revision=1)
        self.assertEqual(derive_scope([ObjectRef('project_resource', str(hidden['id']))]).source_refs,
                         {self.a, self.b})
        second_grant.delete()
        page = self.act(self.actor, 'resource.list', {'project_id': self.project['id'], 'limit': 1}).data
        self.assertEqual(page, {'items': [first], 'next_cursor': first['id']})
        page = self.act(self.actor, 'resource.list',
                        {'project_id': self.project['id'], 'limit': 1, 'cursor': first['id']}).data
        self.assertEqual(page, {'items': [last], 'next_cursor': 0})
        with self.assertRaises(DomainError):
            self.act(self.actor, 'resource.create', payload, key='restricted')

    def test_archived_project_reports_state_conflict(self):
        self.act(self.actor, 'project.archive', {'project_id': self.project['id']}, key='archive', revision=1)
        with self.assertRaises(DomainError) as caught:
            self.act(self.actor, 'resource.create', self.payload, key='r')
        self.assertEqual((caught.exception.code, caught.exception.status), ('project_archived', 409))


class StructuredFieldReviewTests(SimpleTestCase):
    def test_structured_field_honors_declared_validators(self):
        def reject_reserved(value):
            if 'reserved' in value:
                raise ValidationError('Reserved value.')
        class Input(forms.Form):
            refs = schemas.StructuredField(schema={'type': 'array', 'items': {'type': 'string'}},
                                           validators=[reject_reserved])
        with self.assertRaises(DomainError):
            schemas.clean(Input, {'refs': ['reserved']})
        self.assertEqual(schemas.clean(Input, {'refs': []}), {'refs': []})

    def test_invalid_array_bounds_fail_at_registration(self):
        base = {'type': 'array', 'items': {'type': 'string'}}
        for extra in ({'maxItems': True}, {'minItems': -1}, {'maxItems': '2'},
                      {'minItems': 2, 'maxItems': 1}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                schemas.StructuredField(schema={**base, **extra})
