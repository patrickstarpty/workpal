import hashlib
import json

from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import ObjectRef
from workpal.delivery import artifacts
from workpal.work.models import Issue, IssueRequirements


class DeliveryFixtures(AccessFixtures):
    def setUp(self):
        super().setUp()
        self.member.role = 'owner'
        self.member.save()
        self.grant(self.a, read=True, write=True)
        self.grant(self.b, read=True, write=True)
        self.project = self.act(self.actor, 'project.create', {'name': 'Delivery work'}, key='project').data
        self.issue = self.act(self.actor, 'issue.create', {
            'project_id': self.project['id'], 'title': 'Document the result',
            'criteria': [{'key': 'documented', 'text': 'Provide the result document.'}],
            'source_refs': [{'kind': self.a.kind, 'id': self.a.id}],
        }, key='issue').data
        self.subject = {'type': 'issue', 'id': str(self.issue['id'])}

    def published_artifact(self):
        content = b'Human supplied result, not a tool execution event.\x00'
        upload = artifacts.begin(self.actor, {
            'filename': 'result.txt', 'size': len(content), 'media_type': 'text/plain',
            'source_refs': [{'kind': self.b.kind, 'id': self.b.id}],
        })
        artifacts.append(self.actor, upload['id'], 0, content)
        return artifacts.finish(self.actor, upload['id'], hashlib.sha256(content).hexdigest())


class ManualDelivery(DeliveryFixtures, WorkpalCase):
    def test_manual_submission_pins_real_evidence_without_changing_issue(self):
        artifact = self.published_artifact()
        requirements = self.act(self.actor, 'issue.requirements.read', {
            'issue_id': self.issue['id'], 'number': 1,
        }).data
        issue_before = list(Issue.objects.values())
        requirements_before = list(IssueRequirements.objects.values())
        payload = {
            'subject': self.subject, 'requirements_revision': 1,
            'summary': 'Result supplied for review.', 'limitations': 'Human report only.',
            'artifact_ids': [artifact['id']],
            'evidence': [{'criterion_key': 'documented', 'artifact_ids': [artifact['id']],
                          'note': 'Please review the attached document.'}],
        }
        audit_before, outbox_before = AuditEvent.objects.count(), Outbox.objects.count()

        result = self.act(self.actor, 'delivery.submit', payload, key='manual-delivery')

        self.assertEqual(result.state, 'completed')
        data = result.data
        self.assertEqual(result.object_refs, [ObjectRef('delivery', str(data['id']))])
        self.assertEqual((data['number'], data['source'], data['subject'], data['submitted_by']),
                         (1, 'human', self.subject, self.user.pk))
        self.assertEqual(data['requirements_snapshot'], requirements)
        self.assertEqual(data['workflow_snapshot'], self.issue['workflow_snapshot'])
        self.assertEqual(data['artifacts_snapshot'], [artifact])
        self.assertEqual(data['evidence'], payload['evidence'])
        self.assertEqual((data['summary'], data['limitations']),
                         (payload['summary'], payload['limitations']))
        immutable = {key: data[key] for key in (
            'subject', 'source', 'summary', 'limitations', 'requirements_snapshot',
            'workflow_snapshot', 'artifacts_snapshot', 'evidence',
        )}
        expected_hash = hashlib.sha256(json.dumps(immutable, sort_keys=True, separators=(',', ':'),
                                                  ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()
        self.assertEqual(data['sha256'], expected_hash)
        self.assertFalse({'run_id', 'current', 'approved', 'test_passed'} & set(data))
        self.assertEqual((AuditEvent.objects.count(), Outbox.objects.count()),
                         (audit_before + 1, outbox_before + 1))
        self.assertEqual(self.act(self.actor, 'delivery.submit', payload, key='manual-delivery').data, data)
        self.assertEqual(self.act(self.actor, 'delivery.read', {'delivery_id': data['id']}).data, data)
        self.assertEqual(Outbox.objects.count(), outbox_before + 1)
        self.assertEqual(list(Issue.objects.values()), issue_before)
        self.assertEqual(list(IssueRequirements.objects.values()), requirements_before)

class DeliveryCore(DeliveryFixtures, WorkpalCase):
    def payload(self):
        return dict(subject=self.subject, requirements_revision=1, summary='Human result')

    def test_invalid_fields_evidence_and_unpublished_attachment(self):
        from workpal.contracts import DomainError
        upload = artifacts.begin(self.actor, dict(filename='pending',size=1,source_refs=[dict(kind=self.b.kind,id=self.b.id)]))
        for extra in [dict(source='human'),dict(run_id=1),dict(head='abc'),dict(summary=' '),
                      dict(evidence=[dict(criterion_key='missing',artifact_ids=[])]),
                      dict(artifact_ids=[upload['id']]),dict(artifact_ids=[True]),
                      dict(evidence=[dict(criterion_key='documented',artifact_ids=[999])])]:
            with self.subTest(extra=extra), self.assertRaises(DomainError):
                self.act(self.actor,'delivery.submit',dict(self.payload(),**extra),key='invalid')

    def test_executor_cannot_submit_or_replay(self):
        from workpal.contracts import Actor, DomainError
        self.act(self.actor,'delivery.submit',self.payload(),key='human')
        executor=Actor(self.user.pk,self.workspace.pk,executor_id='agent')
        for key in ['human','new']:
            with self.assertRaises(DomainError):
                self.act(executor,'delivery.submit',self.payload(),key=key)

    def test_revoked_artifact_source_blocks_read_and_replay(self):
        from workpal.access.models import SourceGrant
        from workpal.contracts import DomainError
        artifact=self.published_artifact()
        payload=dict(self.payload(),artifact_ids=[artifact['id']])
        delivery=self.act(self.actor,'delivery.submit',payload,key='saved').data
        SourceGrant.objects.filter(user=self.user,source__object_id=self.b.id).delete()
        with self.assertRaises(DomainError): self.act(self.actor,'delivery.read',dict(delivery_id=delivery['id']))
        with self.assertRaises(DomainError): self.act(self.actor,'delivery.submit',payload,key='saved')

    def test_historical_requirements_and_numbering(self):
        first=self.act(self.actor,'delivery.submit',self.payload(),key='first').data
        self.act(self.actor,'issue.update',dict(issue_id=self.issue['id'],title='Changed'),key='update',revision=self.issue['revision'])
        second=self.act(self.actor,'delivery.submit',self.payload(),key='second').data
        self.assertEqual(second['number'],2)
        self.assertEqual(second['requirements_snapshot'],first['requirements_snapshot'])
        self.assertEqual(self.act(self.actor,'delivery.read',dict(delivery_id=first['id'])).data,first)
