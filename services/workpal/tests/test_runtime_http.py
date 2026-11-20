from django.test import TestCase
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership

class RuntimeHTTPTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='http-owner', password='pass')
        self.workspace = Workspace.objects.create(name='HTTP')
        Membership.objects.create(user=self.user, workspace=self.workspace, role='owner')
        self.client.login(username='http-owner', password='pass')
        self.url = f'/api/v1/workspaces/{self.workspace.pk}/runtime-pairings'

    def test_real_issue_post(self):
        self.assertEqual(self.client.post(self.url, {'name':'Device'}, content_type='application/json').status_code, 200)

    def post(self, url, data):
        return self.client.post(url, data, content_type='application/json')

    def paired(self):
        issued = self.post(self.url, {'name':'Device'}).json()
        paired = self.post('/api/runtime/v1/pair', {'version':1,'secret':issued['secret']}).json()
        return issued, paired

    def execute(self, action, payload, revision=None, key=None, actor=None):
        from workpal.actions.registry import execute
        from workpal.contracts import Actor, ActionRequest
        return execute(actor or Actor(self.user.pk,self.workspace.pk), ActionRequest(action,payload,revision,key))

    def test_complete_registry_revoke_and_no_read_outbox(self):
        from workpal.agents import runtime_identity as core
        from workpal.audit.models import Outbox
        from workpal.contracts import DomainError
        issued, paired = self.paired()
        before = Outbox.objects.count()
        read = self.execute('runtime.pairing.read', {'pairing_id':issued['pairing_id']})
        self.assertEqual(read.data['runtime_id'],paired['runtime_id'])
        self.execute('runtime.read', {'runtime_id':paired['runtime_id']})
        self.assertEqual(Outbox.objects.count(),before)
        result = self.execute('runtime.revoke', {'runtime_id':paired['runtime_id']},1,'revoke')
        self.assertTrue(result.data['revoked'])
        with self.assertRaises(DomainError): core.authenticate_runtime(paired['runtime_token'])

    def test_bad_http_inputs(self):
        cases = [('{}',400), ('[]',400), ('{"name":"a","name":"b"}',400),
                 ('{"name":"a","extra":1}',400), ('{"name":NaN}',400),
                 ('{"name":"'+('a'*16384)+'"}',413), ('{',400), ('{"name":"\\ud800"}',400)]
        for body, status in cases:
            response = self.post(self.url, body)
            self.assertEqual(response.status_code,status,body[:30])
            self.assertEqual(response['Cache-Control'],'no-store')
            self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.assertEqual(self.client.get(self.url).status_code,405)
        self.assertEqual(self.client.post(self.url,'{}',content_type='text/plain').status_code,400)
        for version, status in [(True,400),(2,409)]:
            self.assertEqual(self.post('/api/runtime/v1/pair',{'version':version,'secret':'private'}).status_code,status)
        response = self.post('/api/runtime/v1/pair',{'version':1,'secret':'private'})
        self.assertEqual(response.status_code,401)
        self.assertNotIn(b'private',response.content)

    def test_session_csrf_host_tenant_and_member(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        response = client.post('/api/v1/auth/login',{'username':'http-owner','password':'pass'},content_type='application/json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,200)
        self.assertEqual(client.post(self.url,{'name':'Device'},content_type='application/json').status_code,403)
        self.assertEqual(client.post(self.url,{'name':'Device'},content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code,403)
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.assertEqual(client.post(self.url,{'name':'Device'},content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code,200)
        self.assertEqual(client.post('/api/runtime/v1/pair',{'version':1,'secret':'x'},content_type='application/json').status_code,401)
        self.assertEqual(self.client.post(self.url,{'name':'D'},content_type='application/json',HTTP_HOST='evil.invalid').status_code,400)
        other = Workspace.objects.create(name='Other')
        self.assertIn(self.post(f'/api/v1/workspaces/{other.pk}/runtime-pairings',{'name':'D'}).status_code,(403,404))
        Membership.objects.filter(user=self.user).update(role='member')
        self.assertEqual(self.post(self.url,{'name':'D'}).status_code,403)
        self.client.logout()
        self.assertEqual(self.post(self.url,{'name':'D'}).status_code,403)

    def test_response_loss_and_issuer_revocation(self):
        issued, paired = self.paired()
        self.assertEqual(self.post('/api/runtime/v1/pair',{'version':1,'secret':issued['secret']}).status_code,409)
        metadata = self.execute('runtime.pairing.read',{'pairing_id':issued['pairing_id']}).data
        self.assertEqual(metadata['runtime_id'],paired['runtime_id'])
        self.assertNotIn('secret',metadata)
        issued = self.post(self.url,{'name':'Second'}).json()
        Membership.objects.filter(user=self.user).update(role='member')
        self.assertEqual(self.post('/api/runtime/v1/pair',{'version':1,'secret':issued['secret']}).status_code,403)

    def test_registry_replay_current_authority_and_cas(self):
        from workpal.contracts import Actor, DomainError
        from workpal.audit.models import Outbox
        from workpal.access.models import RegisteredObject
        _, paired = self.paired()
        payload = {'runtime_id':paired['runtime_id']}
        for revision,key in [(None,'x'),(1,None),(2,'x')]:
            with self.assertRaises(DomainError): self.execute('runtime.revoke',payload,revision,key)
        first = self.execute('runtime.revoke',payload,1,'same')
        count = Outbox.objects.count()
        self.assertEqual(self.execute('runtime.revoke',payload,1,'same').data,first.data)
        self.assertEqual(Outbox.objects.count(),count)
        for executor in ('', 'worker'):
            with self.assertRaises(DomainError):
                self.execute('runtime.revoke',payload,1,'same',Actor(self.user.pk,self.workspace.pk,executor))
        Membership.objects.filter(user=self.user).update(role='member')
        with self.assertRaises(DomainError): self.execute('runtime.revoke',payload,1,'same')
        Membership.objects.filter(user=self.user).update(role='owner')
        from workpal.access.models import SourceGrant, SourceLink
        source = RegisteredObject.objects.create(workspace=self.workspace,kind='http-source',object_id='1',is_source=True)
        runtime = RegisteredObject.objects.get(kind='runtime',object_id=str(paired['runtime_id']))
        SourceLink.objects.create(derived=runtime,source=source)
        grant = SourceGrant.objects.create(user=self.user,source=source,read=True,write=False)
        with self.assertRaises(DomainError): self.execute('runtime.revoke',payload,1,'same')
        grant.write=True; grant.save()
        self.assertEqual(self.execute('runtime.revoke',payload,1,'same').data,first.data)
        grant.read=False; grant.save()
        with self.assertRaises(DomainError): self.execute('runtime.read',payload)
        RegisteredObject.objects.filter(pk=runtime.pk).update(available=False)
        with self.assertRaises(DomainError): self.execute('runtime.revoke',payload,1,'same')

    def test_actual_audit_failure_rolls_back_and_retry(self):
        from unittest.mock import patch
        from workpal.agents import runtime_identity as core
        from workpal.agents.models import Runtime, RuntimePairing
        from workpal.access.models import RegisteredObject
        from workpal.audit.models import AuditEvent, Outbox
        from workpal.contracts import DomainError
        models = (Runtime,RuntimePairing,RegisteredObject,AuditEvent,Outbox)
        def snapshot(): return [list(model.objects.order_by('pk').values()) for model in models]
        original = core.audit.record
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise DomainError('storage_unavailable','Unavailable.',status=503)
        before = snapshot()
        with patch.object(core.audit,'record',side_effect=fail):
            self.assertEqual(self.post(self.url,{'name':'D'}).status_code,503)
        self.assertEqual(snapshot(),before)
        issued = self.post(self.url,{'name':'D'}).json()
        before = snapshot()
        with patch.object(core.audit,'record',side_effect=fail):
            self.assertEqual(self.post('/api/runtime/v1/pair',{'version':1,'secret':issued['secret']}).status_code,503)
        self.assertEqual(snapshot(),before)
        response = self.post('/api/runtime/v1/pair',{'version':1,'secret':issued['secret']})
        self.assertEqual(response.status_code,200)
        self.assertEqual(Runtime.objects.count(),1)
