"""Public Interface acceptance tests for Task2a evidence persistence."""
from django.test import TestCase
from tests import test_evidence_policy as policy_tests
from workpal.actions.registry import execute
from workpal.contracts import ActionRequest
from workpal.investigation import evidence
from workpal.investigation.models import Source


class EvidencePersistenceTests(TestCase):
    setUp = policy_tests.EvidencePolicyTests.setUp

    def test_upload_authorized_read_roundtrip(self):
        evidence.configure_policy(self.actor, self.source, self.policy, 1)
        source = Source.objects.get(pk=self.source)
        investigation = execute(self.actor, ActionRequest(
            'investigation.start', dict(
                project_id=source.environment.project_id,
                environment_id=source.environment_id,
                service_id=source.allowed_services.get().pk,
                problem='Investigate uploaded evidence', key='investigation'),
            None, 'investigation')).data
        result = evidence.submit_upload(
            self.actor, investigation['id'], self.source,
            b'SECRET-literal evidence', format='text', key='upload')
        self.assertNotIn('content', result)
        read = evidence.read_evidence(self.actor, result['id'])
        self.assertEqual(read['content'], '[REDACTED] evidence')
        self.assertEqual({k: v for k, v in read.items() if k != 'content'}, result)

    def _upload(self,key='upload',content=b'SECRET-literal evidence'):
        source=Source.objects.get(pk=self.source)
        investigation=execute(self.actor,ActionRequest('investigation.start',dict(project_id=source.environment.project_id,environment_id=source.environment_id,service_id=source.allowed_services.get().pk,problem='Upload',key='fixture'),None,'fixture')).data
        return evidence.submit_upload(self.actor,investigation['id'],self.source,content,format='text',key=key)

    def test_policy_timezone_retry(self):
        from workpal.contracts import DomainError
        evidence.configure_policy(self.actor,self.source,self.policy,1)
        first=self._upload()
        source=Source.objects.get(pk=self.source)
        source.environment.timezone='Asia/Shanghai'
        source.environment.save(update_fields=['timezone'])
        evidence.configure_policy(self.actor,self.source,dict(self.policy,redact_literals=[]),2)
        self.assertEqual(self._upload(),first)
        with self.assertRaises(DomainError) as conflict: self._upload(content=b'different')
        self.assertEqual(conflict.exception.status,409)
        for index in range(11):
            latest=self._upload(key='new-'+str(index))
            self.assertEqual(latest['policy_revision'],3)
            self.assertEqual(latest['timezone'],'Asia/Shanghai')

    def test_generic_forgery_and_capability_cleanup(self):
        from workpal.contracts import DomainError
        evidence.configure_policy(self.actor,self.source,self.policy,1)
        result=self._upload()
        self.assertIsNone(evidence._prepared.get())
        payload=dict(investigation_id=result['investigation_id'],source_id=self.source,format='text',timezone='',range_start='',range_end='',raw_sha256=result['raw_sha256'],raw_bytes=result['raw_bytes'])
        with self.assertRaises(DomainError) as denied:
            execute(self.actor,ActionRequest('evidence.upload',payload,None,'upload'))
        self.assertEqual(denied.exception.status,403)
        self.assertIsNone(evidence._prepared.get())

    def test_real_record_failure_rolls_back(self):
        from unittest.mock import patch
        from workpal.actions import registry
        from workpal.contracts import DomainError
        from workpal.investigation.models import EvidenceSnapshot
        evidence.configure_policy(self.actor,self.source,self.policy,1)
        self._upload(key='setup')
        from django.apps import apps
        def counts(): return {model._meta.label:model.objects.count() for model in apps.get_models()}
        before=counts()
        original=registry.record
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise DomainError('unavailable','Unavailable.',status=503)
        with patch.object(registry,'record',side_effect=fail):
            with self.assertRaises(DomainError): self._upload(key='rollback')
        self.assertEqual(counts(),before)
        self.assertIsNone(evidence._prepared.get())
        self._upload(key='rollback')
        self.assertEqual(EvidenceSnapshot.objects.filter(key='rollback').count(),1)
