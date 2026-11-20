import json
from dataclasses import replace
from django import forms
from django.test import TransactionTestCase, Client
from workpal.actions import registry
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult
from workpal.identity.models import Workspace
from workpal.audit.models import AuditEvent, Outbox
from .access_support import AccessFixtures

class ActionHTTPTests(AccessFixtures, TransactionTestCase):
    def setUp(self):
        super().setUp()
        previous = registry._specs.copy()
        self.addCleanup(lambda: (registry._specs.clear(), registry._specs.update(previous)))
        registry._specs.clear()
        class Input(forms.Form):
            name = forms.CharField(max_length=30)
        def write(actor, payload, revision):
            Workspace.objects.create(name=payload['name'])
            return ActionResult('completed', [], {'name': payload['name']})
        self.spec = ActionSpec('http.write', Input, {'type':'object','properties':{'name':{'type':'string'}},'required':['name'],'additionalProperties':False}, write, lambda a,p: [], mutating=True)
        registry.register(self.spec)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.token = self.client.get('/api/v1/auth/csrf').json()['csrf_token']

    def post(self, body=None, **kwargs):
        return self.client.post('/api/v1/actions/http.write', json.dumps(body if body is not None else {'workspace_id':self.workspace.pk,'payload':{'name':'written'},'idempotency_key':'key'}), content_type='application/json', HTTP_X_CSRFTOKEN=self.token, **kwargs)

    def test_write_replay_conflict(self):
        result = self.post()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.post().json(), result.json())
        self.assertEqual(Workspace.objects.filter(name='written').count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)
        self.assertEqual(Outbox.objects.count(), 1)
        self.assertEqual(self.post({'workspace_id':self.workspace.pk,'payload':{'name':'changed'},'idempotency_key':'key'}).status_code,409)

    def test_invalid_envelopes(self):
        for body in [[], None, {}, {'workspace_id':True,'payload':{}}, {'workspace_id':self.workspace.pk,'payload':{},'actor':1}, {'workspace_id':self.workspace.pk,'payload':{},'expected_revision':True}]:
            if body is None: body = 4
            self.assertEqual(self.post(body).status_code,400)
        self.assertFalse(Outbox.objects.exists())

    def test_confirmation(self):
        registry._specs[self.spec.action_id] = replace(self.spec, confirmation_required=True)
        pending = self.post().json()
        self.assertEqual(pending['state'],'waiting_confirmation')
        self.assertFalse(Workspace.objects.filter(name='written').exists())
        body = {'workspace_id':self.workspace.pk,'payload':{'name':'written'},'idempotency_key':'key','confirmation_id':pending['data']['confirmation_id']}
        self.assertEqual(self.post(body).status_code,200)
        self.assertEqual(self.post(body).status_code,200)
        self.assertEqual(Outbox.objects.count(),1)

    def test_failure_rolls_back(self):
        def fail(*args):
            Workspace.objects.create(name='secret')
            raise RuntimeError('password SQL secret')
        registry._specs[self.spec.action_id] = replace(self.spec,handler=fail)
        response = self.post()
        self.assertEqual(response.status_code,500)
        self.assertNotIn('secret',response.content.decode())
        self.assertFalse(Workspace.objects.filter(name='secret').exists())

    def test_security_and_catalog(self):
        self.assertEqual(self.client.get('/api/v1/actions',{'workspace_id':self.workspace.pk}).status_code,200)
        self.assertEqual(self.client.get('/api/v1/actions/http.write').status_code,405)
        self.assertEqual(self.post(HTTP_HOST='evil.invalid').status_code,400)
        self.assertEqual(self.client.post('/api/v1/actions/http.write',{},content_type='application/json').status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get('/api/v1/actions',{'workspace_id':self.workspace.pk}).status_code,403)

    def test_source_revocation_blocks_new_and_replayed_calls(self):
        grant = self.grant(self.a, read=True, write=True)
        registry._specs[self.spec.action_id] = replace(self.spec, capability='write',resolve_refs=lambda a,p:[self.a])
        self.assertEqual(self.post().status_code,200)
        grant.delete()
        self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.post({'workspace_id':self.workspace.pk,'payload':{'name':'new'},'idempotency_key':'new'}).status_code,403)
        self.assertEqual(Outbox.objects.count(),1)

    def test_current_membership_active_user_and_catalog_roles(self):
        registry._specs[self.spec.action_id] = replace(self.spec,allowed_roles=('owner',))
        url = '/api/v1/actions'
        self.assertEqual(self.client.get(url,{'workspace_id':self.workspace.pk}).json(),{'actions':[]})
        self.member.role = 'owner'
        self.member.save()
        self.assertEqual(len(self.client.get(url,{'workspace_id':self.workspace.pk}).json()['actions']),1)
        self.member.delete()
        # Registry deliberately hides workspaces from nonmembers.
        self.assertEqual(self.post().status_code,404)
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get(url,{'workspace_id':self.workspace.pk}).status_code,403)

    def test_raw_json_query_and_size_validation(self):
        for raw in ['{"workspace_id":1,"workspace_id":2,"payload":{}}','{"workspace_id":1,"payload":{"name":NaN}}','{"workspace_id":1,"payload":{"name":1e999}}','{','null']:
            response = self.client.post('/api/v1/actions/http.write',raw,content_type='application/json',HTTP_X_CSRFTOKEN=self.token)
            self.assertEqual(response.status_code,400)
        for query in ['', '?workspace_id=1&workspace_id=1','?workspace_id=1&user_id=1','?workspace_id=true']:
            self.assertEqual(self.client.get('/api/v1/actions'+query).status_code,400)
        self.assertEqual(self.client.get('/api/v1/actions',{'workspace_id':self.workspace.pk},HTTP_HOST='evil.invalid').status_code,400)
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=10):
            self.assertEqual(self.post().status_code,413)
        self.assertFalse(Outbox.objects.exists())

    def test_direct_registry_result_and_error_match(self):
        from dataclasses import asdict
        from workpal.contracts import ActionRequest, DomainError
        direct = registry.execute(self.actor,ActionRequest('http.write',{'name':'written'},None,'key'))
        self.assertEqual(self.post().json(),asdict(direct))
        body = {'workspace_id':self.workspace.pk,'payload':{'name':'different'},'idempotency_key':'key'}
        try:
            registry.execute(self.actor,ActionRequest('http.write',body['payload'],None,'key'))
        except DomainError as exc:
            response = self.post(body)
            self.assertEqual(response.status_code,exc.status)
            self.assertEqual(response.json()['code'],exc.code)
            self.assertEqual(response.json()['message'],exc.message)
