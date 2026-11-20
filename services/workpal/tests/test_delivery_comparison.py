from tests.support import WorkpalCase
from tests.test_delivery import DeliveryFixtures

class DeliveryComparison(DeliveryFixtures, WorkpalCase):
    def test_registry_same_delivery(self):
        row = self.act(self.actor, 'delivery.submit', dict(subject=self.subject, requirements_revision=1, summary='original'), key='comparison').data
        result = self.act(self.actor, 'delivery.compare', dict(before_delivery_id=row['id'], after_delivery_id=row['id'])).data
        self.assertEqual(result['text_changes'], [])
        self.assertFalse(result['workflow_changed'])
        for field in ('criteria', 'artifacts', 'evidence'):
            self.assertEqual(result[field]['changed'], [])
            self.assertEqual(result[field]['added'], [])
            self.assertEqual(result[field]['removed'], [])

    def pair(self):
        from workpal.delivery import service
        from workpal.contracts import SubjectRef
        return [service.submit(self.actor, SubjectRef(**self.subject), dict(requirements_revision=1, summary=s)) for s in ('old', 'new')]

    def test_text_reverse_and_independent_copy(self):
        from workpal.delivery.comparison import compare
        a, b = self.pair()
        result = compare(self.actor, a['id'], b['id'])
        self.assertEqual(result['text_changes'], [dict(field='summary', before='old', after='new')])
        self.assertEqual(compare(self.actor,b['id'],a['id'])['text_changes'], [dict(field='summary',before='new',after='old')])
        result['criteria']['before_order'].clear()
        self.assertEqual(compare(self.actor,a['id'],b['id'])['criteria']['before_order'], ['documented'])

    def test_strict_ids_and_closed_input(self):
        from workpal.contracts import DomainError
        from workpal.delivery.comparison import compare
        from workpal.storage import MAX_SQLITE_INTEGER
        a, b = self.pair()
        for value in (True, None, '1', 0, -1, MAX_SQLITE_INTEGER, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(DomainError): compare(self.actor,value,b['id'])
                with self.assertRaises(DomainError): self.act(self.actor,'delivery.compare',dict(before_delivery_id=a['id'],after_delivery_id=value))
        with self.assertRaises(DomainError):
            self.act(self.actor,'delivery.compare',dict(before_delivery_id=a['id'],after_delivery_id=b['id'],extra=1))

    def test_logical_artifact_identity_and_evidence(self):
        from workpal.delivery import service
        from workpal.delivery.comparison import compare
        from workpal.contracts import SubjectRef
        first, second = self.published_artifact(), self.published_artifact()
        rows = [service.submit(self.actor, SubjectRef(**self.subject), dict(requirements_revision=1, summary='same',artifact_ids=[artifact['id']],evidence=[dict(criterion_key='documented',artifact_ids=[artifact['id']])])) for artifact in (first,second)]
        result=compare(self.actor,rows[0]['id'],rows[1]['id'])
        self.assertEqual(result['artifacts']['removed'],[first])
        self.assertEqual(result['artifacts']['added'],[second])
        self.assertEqual(result['evidence']['changed'][0]['before']['note'],'')

    def test_revoked_source_on_either_side(self):
        from workpal.access.models import SourceGrant
        from workpal.contracts import DomainError
        a,b=self.pair()
        SourceGrant.objects.filter(source__object_id=self.a.id).update(read=False)
        for ids in ((a['id'],b['id']),(b['id'],a['id'])):
            with self.assertRaises(DomainError):
                self.act(self.actor,'delivery.compare',dict(zip(('before_delivery_id','after_delivery_id'),ids)))

    def test_no_blob_and_single_snapshot_query(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        a,b=self.pair()
        with CaptureQueriesContext(connection) as queries:
            self.act(self.actor,'delivery.compare',dict(before_delivery_id=a['id'],after_delivery_id=b['id']))
        sql=[q['sql'].lower() for q in queries]
        self.assertFalse(any('blob' in q for q in sql))
        snapshots=[q for q in sql if 'select' in q and '"delivery_delivery"."summary"' in q]
        self.assertEqual(len(snapshots),1)

    def test_readonly_executor_and_audit(self):
        from workpal.contracts import Actor
        from workpal.access.models import SourceGrant
        from workpal.audit.models import AuditEvent, Outbox
        a,b=self.pair()
        self.member.role='member'; self.member.save()
        SourceGrant.objects.all().update(write=False)
        count=Outbox.objects.count()
        payload=dict(before_delivery_id=a['id'],after_delivery_id=b['id'])
        self.act(Actor(self.user.pk,self.workspace.pk,executor_id='reader'), 'delivery.compare',payload)
        event=AuditEvent.objects.filter(action_id='delivery.compare').get()
        self.assertEqual(event.fields,payload)
        self.assertIn(dict(kind=self.a.kind,id=self.a.id),event.scope_refs)
        self.assertEqual(Outbox.objects.count(),count)

    def test_late_audit_failure_rolls_back_all_tables(self):
        from unittest.mock import patch
        from django.apps import apps
        from workpal.audit import service as audit
        a,b=self.pair()
        def snapshot():
            return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()}
        before=snapshot()
        original=audit.record
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise RuntimeError('late audit failure')
        with patch('workpal.actions.registry.record',side_effect=fail):
            with self.assertRaises(RuntimeError):
                self.act(self.actor,'delivery.compare',dict(before_delivery_id=a['id'],after_delivery_id=b['id']))
        self.assertEqual(snapshot(),before)

    def test_missing_cross_workspace_and_subject(self):
        from workpal.contracts import Actor, DomainError
        from workpal.identity.models import Membership
        a,b=self.pair()
        other=self.act(self.actor,'issue.create',dict(project_id=self.project['id'],title='other'),key='other-subject').data
        c=self.act(self.actor,'delivery.submit',dict(subject=dict(type='issue',id=str(other['id'])),requirements_revision=1,summary='other'),key='other-delivery').data
        for after,status in ((c['id'],409),(999999,404)):
            with self.assertRaises(DomainError) as raised:
                self.act(self.actor,'delivery.compare',dict(before_delivery_id=a['id'],after_delivery_id=after))
            self.assertEqual(raised.exception.status,status)
        Membership.objects.create(user=self.user,workspace=self.other,role='member')
        with self.assertRaises(DomainError) as raised:
            self.act(Actor(self.user.pk,self.other.pk),'delivery.compare',dict(before_delivery_id=a['id'],after_delivery_id=b['id']))
        self.assertEqual(raised.exception.status,404)

    def test_registry_reports_collection_reordering_without_content_changes(self):
        criteria=[dict(key='alpha',text='First criterion'),dict(key='beta',text='Second criterion')]
        updated=self.act(self.actor,'issue.update',dict(issue_id=self.issue['id'],criteria=criteria),key='order-requirements',revision=1).data
        first,second=self.published_artifact(),self.published_artifact()
        evidence=[dict(criterion_key='alpha',artifact_ids=[first['id']]),dict(criterion_key='beta',artifact_ids=[second['id']])]
        payload=dict(subject=self.subject,requirements_revision=updated['requirements_revision'],summary='Same content',
            artifact_ids=[first['id'],second['id']],evidence=evidence)
        before=self.act(self.actor,'delivery.submit',payload,key='before-order').data
        updated=self.act(self.actor,'issue.update',dict(issue_id=self.issue['id'],criteria=list(reversed(criteria))),key='reverse-requirements',revision=updated['revision']).data
        payload.update(requirements_revision=updated['requirements_revision'],artifact_ids=[second['id'],first['id']],evidence=list(reversed(evidence)))
        after=self.act(self.actor,'delivery.submit',payload,key='after-order').data
        result=self.act(self.actor,'delivery.compare',dict(before_delivery_id=before['id'],after_delivery_id=after['id'])).data
        self.assertEqual(result['text_changes'],[])
        for field in ('criteria','artifacts','evidence'):
            self.assertEqual(result[field]['added'],[])
            self.assertEqual(result[field]['removed'],[])
            self.assertEqual(result[field]['changed'],[])
            self.assertEqual(result[field]['after_order'],list(reversed(result[field]['before_order'])))

    def test_real_requirements_changes_and_future_rebinding_preserve_history(self):
        from workpal.delivery.comparison import compare
        a,_=self.pair()
        updated=self.act(self.actor,'issue.update',dict(issue_id=self.issue['id'],title='Changed title',description='New description',criteria=[dict(key='new',text='Added')]),key='comparison-update',revision=self.issue['revision']).data
        b=self.act(self.actor,'delivery.submit',dict(subject=self.subject,requirements_revision=updated['requirements_revision'],summary='new'),key='updated-delivery').data
        result=compare(self.actor,a['id'],b['id'])
        self.assertEqual([i['field'] for i in result['text_changes']],['summary','requirements.title','requirements.description'])
        self.assertEqual(result['criteria']['added'],[dict(key='new',text='Added')])
        self.assertEqual(result['criteria']['removed'],self.issue['criteria'])
        self.act(self.actor,'issue.update',dict(issue_id=self.issue['id'],title='Later title'),key='later-update',revision=updated['revision'])
        from workpal.workflows import service as workflows
        from workpal.work import service as projects
        draft=workflows.create(self.actor,'New published workflow')
        version=workflows.publish(self.actor,draft['id'],draft['revision'])
        projects.set_workflow(self.actor,self.project['id'],version['id'],self.project['revision'])
        self.assertEqual(projects.snapshot_workflow(self.actor,self.project['id'])['version_id'],version['id'])
        self.assertEqual(compare(self.actor,a['id'],b['id']),result)
