from copy import deepcopy

from django.apps import apps
from tests.support import WorkpalCase
from tests.test_delivery import DeliveryFixtures
from workpal.access.models import SourceGrant
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import Actor, DomainError, ObjectRef, SubjectRef
from workpal.delivery import service
from workpal.identity.models import Membership
from workpal.work import issues, service as projects


class ComparisonReview(DeliveryFixtures, WorkpalCase):
    def submit(self, key, **values):
        payload = dict(subject=self.subject, requirements_revision=self.issue['requirements_revision'], summary=key)
        payload.update(values)
        return self.act(self.actor, 'delivery.submit', payload, key=key).data

    def compare(self, before, after, actor=None):
        return self.act(actor or self.actor, 'delivery.compare',
            dict(before_delivery_id=before['id'], after_delivery_id=after['id']))

    def snapshot(self):
        return {m._meta.label: list(m.objects.order_by('pk').values()) for m in apps.get_models()}

    def test_public_interface_reports_all_actual_collection_and_text_changes(self):
        old_criteria = [dict(key='change', text='Old condition'), dict(key='keep', text='Stable'),
                        dict(key='remove', text='Removed condition')]
        new_criteria = [dict(key='add', text='New condition'), old_criteria[1], dict(key='change', text='New wording')]
        self.issue = self.act(self.actor, 'issue.update', dict(issue_id=self.issue['id'],
            title='Before title', description='Before description', criteria=old_criteria), key='before-requirements', revision=1).data
        retained, removed, added = [self.published_artifact() for _ in range(3)]
        self.assertEqual(removed['sha256'], added['sha256'])
        self.assertNotEqual(removed['id'], added['id'])
        old_evidence = [dict(criterion_key='change', artifact_ids=[retained['id']], note='Old human report'),
                        dict(criterion_key='keep', artifact_ids=[retained['id']], note='Unchanged report'),
                        dict(criterion_key='remove', artifact_ids=[removed['id']], note='Removed report')]
        new_evidence = [dict(criterion_key='add', artifact_ids=[added['id']], note='Added report'),
                        old_evidence[1], dict(criterion_key='change', artifact_ids=[added['id'], retained['id']], note='New human report')]
        before = self.submit('before', summary='Before summary', limitations='Before limitations',
                             artifact_ids=[retained['id'], removed['id']], evidence=old_evidence)
        self.issue = self.act(self.actor, 'issue.update', dict(issue_id=self.issue['id'], title='After title',
            description='After description', criteria=new_criteria), key='after-requirements', revision=self.issue['revision']).data
        after = self.submit('after', summary='After summary', limitations='After limitations',
                            artifact_ids=[added['id'], retained['id']], evidence=new_evidence)
        result = self.compare(before, after).data
        self.assertEqual([item['field'] for item in result['text_changes']],
                         ['summary', 'limitations', 'requirements.title', 'requirements.description'])
        self.assertEqual([item['before'] for item in result['text_changes']],
                         ['Before summary', 'Before limitations', 'Before title', 'Before description'])
        self.assertEqual(result['criteria'], dict(added=[new_criteria[0]], removed=[old_criteria[2]],
            changed=[dict(key='change', before=old_criteria[0], after=new_criteria[2])],
            before_order=['change', 'keep', 'remove'], after_order=['add', 'keep', 'change']))
        self.assertEqual(result['artifacts'], dict(added=[added], removed=[removed], changed=[],
            before_order=[retained['id'], removed['id']], after_order=[added['id'], retained['id']]))
        self.assertEqual(result['evidence'], dict(added=[new_evidence[0]], removed=[old_evidence[2]],
            changed=[dict(criterion_key='change', before=old_evidence[0], after=new_evidence[2])],
            before_order=['change', 'keep', 'remove'], after_order=['add', 'keep', 'change']))
        self.assertEqual((result['before']['requirements_revision'], result['after']['requirements_revision']), (2, 3))
        self.assertFalse(result['workflow_changed'])
        reversed_result = self.compare(after, before).data
        for field in ('criteria', 'artifacts', 'evidence'):
            self.assertEqual(reversed_result[field]['added'], result[field]['removed'])
            self.assertEqual(reversed_result[field]['removed'], result[field]['added'])
            self.assertEqual(reversed_result[field]['after_order'], result[field]['before_order'])
        self.assertEqual(reversed_result['evidence']['changed'][0]['before'], new_evidence[2])
        same = self.compare(after, after)
        self.assertEqual(same.object_refs, [issues.ref(self.issue['id']), service.ref(after['id'])])
        for field in ('criteria', 'artifacts', 'evidence'):
            self.assertEqual([same.data[field][key] for key in ('added', 'removed', 'changed')], [[], [], []])
        expected = deepcopy(result)
        result['artifacts']['added'][0]['filename'] = 'Caller mutation'
        result['evidence']['changed'][0]['before']['artifact_ids'].clear()
        self.assertEqual(self.compare(before, after).data, expected)
        self.assertEqual(service.read(self.actor, before['id']), before)

    def test_independent_sources_on_either_side_are_required_and_audited_for_readonly_executor(self):
        left_source = self.register(self.workspace.pk, ObjectRef('source', 'comparison-left'), is_source=True)
        right_source = self.register(self.workspace.pk, ObjectRef('source', 'comparison-right'), is_source=True)
        left_grant = self.grant(left_source, read=True, write=True)
        right_grant = self.grant(right_source, read=True, write=True)
        before = self.submit('Private left text', source_refs=[dict(kind=left_source.kind, id=left_source.id)])
        after = self.submit('Private right text', source_refs=[dict(kind=right_source.kind, id=right_source.id)])
        self.member.role = 'member'
        self.member.save()
        SourceGrant.objects.filter(user=self.user).update(write=False)
        reader = Actor(self.user.pk, self.workspace.pk, executor_id='comparison-reader')
        outbox_before = Outbox.objects.count()
        result = self.compare(before, after, reader)
        self.assertEqual(result.object_refs, [issues.ref(self.issue['id']), service.ref(before['id']), service.ref(after['id'])])
        event = AuditEvent.objects.get(action_id='delivery.compare')
        self.assertTrue({self.a, left_source, right_source} <= {ObjectRef(**ref) for ref in event.scope_refs})
        self.assertEqual(event.fields, dict(before_delivery_id=before['id'], after_delivery_id=after['id']))
        self.assertEqual(Outbox.objects.count(), outbox_before)
        for grant in (left_grant, right_grant):
            grant.read = False
            grant.save(update_fields=['read'])
            state = self.snapshot()
            for one, two in ((before, after), (after, before)):
                with self.subTest(source=grant.pk), self.assertRaises(DomainError) as caught:
                    self.compare(one, two, reader)
                self.assertEqual(caught.exception.status, 403)
            self.assertEqual(self.snapshot(), state)
            grant.read = True
            grant.save(update_fields=['read'])

    def test_mixed_workspace_pair_never_returns_the_authorized_half(self):
        local = self.submit('Local content')
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        foreign_actor = Actor(self.user.pk, self.other.pk)
        project = projects.create(foreign_actor, 'Foreign project')
        task = issues.create(foreign_actor, project['id'], 'Foreign subject')
        foreign = service.submit(foreign_actor, SubjectRef('issue', str(task['id'])),
                                 dict(requirements_revision=1, summary='Foreign content'))
        state = self.snapshot()
        for actor in (self.actor, foreign_actor):
            for one, two in ((local, foreign), (foreign, local)):
                with self.subTest(actor=actor.workspace_id), self.assertRaises(DomainError) as caught:
                    self.compare(one, two, actor)
                self.assertEqual(caught.exception.status, 404)
                self.assertEqual(caught.exception.details, {})
        self.assertEqual(self.snapshot(), state)
