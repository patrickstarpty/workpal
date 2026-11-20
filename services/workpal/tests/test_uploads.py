from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.db import connections
from django.test import TransactionTestCase
from tests.support import WorkpalCase
from tests.access_support import AccessFixtures
from workpal.contracts import Actor, DomainError
from workpal.delivery import artifacts as a
from workpal.delivery.models import Upload, UploadChunk

class UploadBehavior(AccessFixtures, WorkpalCase):
    def begin(self, **kw): return a.begin(self.actor, dict(filename='文件', size=6, **kw))['id']
    def test_resume_and_old_retry(self):
        pk=self.begin()
        self.assertEqual(a.append(self.actor,pk,0,b'abc'),3)
        self.assertEqual(a.append(self.actor,pk,3,b'def'),6)
        self.assertEqual(a.append(self.actor,pk,0,b'abc'),6)
        self.assertEqual(UploadChunk.objects.count(),2)
    def test_conflicts_have_no_partial_write(self):
        pk=self.begin(); a.append(self.actor,pk,0,b'abc')
        for offset,chunk in [(4,b'x'),(1,b'x'),(0,b'xxx'),(3,b'toolong')]:
            with self.assertRaises(DomainError) as caught: a.append(self.actor,pk,offset,chunk)
            self.assertEqual(caught.exception.status,409)
        self.assertEqual(a.status(self.actor,pk)['offset'],3)
        self.assertEqual(UploadChunk.objects.count(),1)
    def test_metadata_strict(self):
        for fields in [dict(filename='',size=0),dict(filename='x\n',size=0),dict(filename='\ud800',size=0),dict(filename='x',size=True),dict(filename='x',size=0,extra=1),dict(filename='x',size=0,source_refs=False),dict(filename='x',size=0,media_type=''),dict(filename='x',size=0,media_type='text/é')]:
            with self.assertRaises(DomainError): a.begin(self.actor,fields)
        self.assertEqual(Upload.objects.count(),0)
    def test_byte_limits(self):
        pk=a.begin(self.actor,dict(filename='x',size=a.MAX_SIZE))['id']
        for offset,chunk in [(True,b'x'),(0,b''),(0,bytearray(b'x')),(0,b'x'*(a.MAX_CHUNK+1))]:
            with self.assertRaises(DomainError): a.append(self.actor,pk,offset,chunk)
        self.assertEqual(a.append(self.actor,pk,0,b'x'*a.MAX_CHUNK),a.MAX_CHUNK)
    def test_wrong_owner_workspace_and_membership(self):
        from django.contrib.auth import get_user_model
        from workpal.identity.models import Membership
        pk=self.begin()
        other=get_user_model().objects.create(username='admin')
        Membership.objects.create(user=other,workspace=self.workspace,role='owner')
        for actor in [Actor(other.pk,self.workspace.pk),Actor(self.user.pk,self.other.pk)]:
            with self.assertRaises(DomainError) as caught: a.status(actor,pk)
            self.assertEqual(caught.exception.status,404)
        self.member.delete()
        with self.assertRaises(DomainError): a.status(self.actor,pk)
    def test_source_revocation_and_cached_begin(self):
        grant=self.grant(self.a,read=True,write=True)
        payload=dict(filename='x',size=0,source_refs=[dict(kind='source',id='a')])
        result=self.act(self.actor,'artifact.upload.begin',payload,key='same')
        self.assertEqual(result.data,self.act(self.actor,'artifact.upload.begin',payload,key='same').data)
        grant.delete()
        for operation in [lambda:a.status(self.actor,result.data['id']),lambda:self.act(self.actor,'artifact.upload.begin',payload,key='same')]:
            with self.assertRaises(DomainError) as caught: operation()
            self.assertEqual(caught.exception.status,403)
    def test_registration_rollback(self):
        with patch('workpal.delivery.artifacts.register_object',side_effect=RuntimeError('fault')):
            with self.assertRaises(RuntimeError): self.begin()
        self.assertEqual(Upload.objects.count(),0)
        self.begin()
    def test_audit_rollback_and_key_retry(self):
        payload=dict(filename='x',size=0)
        with patch('workpal.actions.registry.record',side_effect=RuntimeError('fault')):
            with self.assertRaises(RuntimeError): self.act(self.actor,'artifact.upload.begin',payload,key='retry')
        self.assertEqual(Upload.objects.count(),0)
        self.act(self.actor,'artifact.upload.begin',payload,key='retry')
        self.assertEqual(Upload.objects.count(),1)

class UploadConcurrency(AccessFixtures, TransactionTestCase):
    def race(self, chunks):
        pk=a.begin(self.actor,dict(filename='x',size=3))['id']; barrier=Barrier(2)
        def run(chunk):
            connections.close_all()
            try:
                connection=connections['default']; connection.ensure_connection()
                identity=id(connection.connection)
                barrier.wait(timeout=10)
                try: return identity,a.append(self.actor,pk,0,chunk)
                except DomainError as error: return identity,error.status
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(run,chunks))
        self.assertNotEqual(results[0][0],results[1][0])
        self.assertEqual(UploadChunk.objects.filter(upload_id=pk).count(),1)
        self.assertEqual(a.status(self.actor,pk)['offset'],3)
        return sorted(value for _,value in results)
    def test_same_bytes(self): self.assertEqual(self.race([b'abc',b'abc']),[3,3])
    def test_different_bytes(self): self.assertEqual(self.race([b'abc',b'def']),[3,409])
