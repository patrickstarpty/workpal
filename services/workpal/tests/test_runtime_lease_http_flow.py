from datetime import datetime, timezone, timedelta
from hashlib import sha256
from unittest.mock import patch
from django.apps import apps
from django.test import Client, TransactionTestCase
from tests.access_support import AccessFixtures
from workpal.actions.registry import execute
from workpal.contracts import ActionRequest, DomainError
from workpal.execution import leases, service as runs
from workpal.execution.models import Run, TaskToken
from workpal.work import service as projects, issues
from workpal.audit.models import AuditEvent, Outbox


class LeaseHTTPFlowTests(AccessFixtures, TransactionTestCase):
    def post(self, url, data, secret=None, client=None, **headers):
        if secret:
            headers['HTTP_AUTHORIZATION'] = 'Bearer ' + secret
        return (client or self.browser).post(url, data, content_type='application/json', **headers)

    def setUp(self):
        super().setUp()
        self.member.role = 'owner'; self.member.save()
        self.user.set_password('pass'); self.user.save()
        self.browser = Client(enforce_csrf_checks=True)
        token = self.browser.get('/api/v1/auth/csrf').json()['csrf_token']
        self.assertEqual(self.post('/api/v1/auth/login', dict(username='reader', password='pass'), HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.csrf = self.browser.get('/api/v1/auth/csrf').json()['csrf_token']
        self.pair_url = f'/api/v1/workspaces/{self.workspace.pk}/runtime-pairings'
        issued = self.post(self.pair_url, {'name':'Device'}, HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(issued.status_code, 200)
        self.anon = Client(enforce_csrf_checks=True)
        paired = self.post('/api/runtime/v1/pair', dict(version=1, secret=issued.json()['secret']), client=self.anon)
        self.assertEqual(paired.status_code, 200)
        self.device = paired.json()
        def action(name, payload, revision=None, key=None):
            return execute(self.actor, ActionRequest(name, payload, revision, key)).data
        self.agent = action('agent.create', {'name':'Builder'}, key='create')
        action('runtime.bind', {'agent_id':self.agent['id'], 'runtime_id':self.device['runtime_id']}, 1, 'bind')
        project = projects.create(self.actor, 'Project')
        issue = issues.create(self.actor, project['id'], 'Private input marker')
        self.row = Run.objects.get(pk=runs.start(self.actor, {'type':'issue','id':issue['id']}, self.agent['id'], 'start')['id'])
        self.claim_url = '/api/runtime/v1/claim'
        self.renew_url = f'/api/runtime/v1/runs/{self.row.pk}/renew'
        self.payload = dict(version=1, capabilities=dict(provider_key='copilot_cli', version=1, installed=True, authenticated=True, execution_ready=True))
        self.now = datetime.now(timezone.utc)
        self.enterContext(patch.object(leases, '_clock', return_value=self.now))

    def snapshot(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()}

    def claim(self):
        return self.post(self.claim_url, self.payload, self.device['runtime_token'], self.anon)

    def renew(self, token):
        return self.post(self.renew_url, dict(version=1, epoch=1), token, self.anon)

    def counts(self, claims, renews):
        for action, count in [('runtime.claim', claims), ('runtime.renew', renews)]:
            events = AuditEvent.objects.filter(action_id=action)
            self.assertEqual(events.count(), count)
            self.assertEqual(Outbox.objects.filter(event__in=events).count(), count)

    def state(self, revision, token):
        self.row.refresh_from_db()
        self.assertEqual((self.row.status,self.row.lease_epoch,self.row.revision), ('dispatched',1,revision))
        self.assertEqual(self.row.lease_expires_at, self.now+timedelta(seconds=45))
        live = TaskToken.objects.get(revoked_at=None)
        self.assertEqual(live.secret_hash, sha256(token.encode()).hexdigest())
        self.assertEqual(live.expires_at, self.now+timedelta(seconds=60))

    def stale(self, token):
        before = self.snapshot()
        for _ in range(2): self.assertEqual(self.renew(token).status_code, 401)
        self.assertEqual(before, self.snapshot())

    def test_claim_rotate_and_revoked_creator_stop(self):
        before = self.snapshot()
        self.assertEqual(self.claim().status_code, 409)
        self.assertEqual(before, self.snapshot())
        with patch.object(leases, '_verify_capabilities', return_value=True):
            response = self.claim(); self.assertEqual(response.status_code,200)
            first = response.json()['lease']['task_token']
            self.state(2,first); self.counts(1,0)
            response = self.renew(first); self.assertEqual(response.status_code,200)
            second = response.json()['lease']['task_token']
            self.state(3,second); self.counts(1,1); self.stale(first)
            self.member.delete()
            response = self.renew(second)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['kind'],'stop_only')
            self.assertEqual(response.json()['reason'],'authorization_revoked')
            self.row.refresh_from_db()
            self.assertEqual(self.row.revision,4)
            self.assertEqual(TaskToken.objects.filter(revoked_at=None).count(),0)
            self.counts(1,2); self.stale(second)
            saved = repr(list(AuditEvent.objects.filter(action_id__startswith='runtime.').values())) + repr(list(Outbox.objects.values()))
            for secret in (first, second, self.device['runtime_token']):
                self.assertNotIn(secret,saved); self.assertNotIn(sha256(secret.encode()).hexdigest(),saved)
            self.assertNotIn('Private input marker',saved)

    def test_credential_and_session_separation(self):
        with patch.object(leases, '_verify_capabilities', return_value=True):
            response = self.claim(); self.assertEqual(response.status_code,200)
            task = response.json()['lease']['task_token']
            before = self.snapshot()
            self.assertEqual(self.renew(self.device['runtime_token']).status_code,401)
            self.assertEqual(self.post(self.claim_url,self.payload,task).status_code,401)
            self.assertEqual(self.post(self.claim_url,self.payload).status_code,401)
            self.assertEqual(self.post(self.renew_url,dict(version=1,epoch=1)).status_code,401)
            self.assertEqual(self.post(self.pair_url,{'name':'No csrf'}).status_code,403)
            envelope = dict(workspace_id=self.workspace.pk,payload={'runtime_id':self.device['runtime_id']})
            self.assertEqual(self.post('/api/v1/actions/runtime.read',envelope,task,self.anon).status_code,403)
            self.assertEqual(before,self.snapshot())
            good = self.post('/api/v1/actions/runtime.read',envelope,HTTP_X_CSRFTOKEN=self.csrf)
            self.assertEqual(good.status_code,200)
            self.assertEqual(self.renew(task).status_code,200)

    def test_actual_audit_failure_rollback_retry_and_response_loss(self):
        original = leases.audit.record
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('storage_unavailable','private failure marker',status=503)
        with patch.object(leases, '_verify_capabilities', return_value=True):
            for operation in ('claim','renew'):
                before = self.snapshot()
                with patch.object(leases.audit,'record',side_effect=fail):
                    response = self.claim() if operation=='claim' else self.renew(token)
                self.assertEqual(response.status_code,503)
                self.assertNotIn(b'private failure marker',response.content)
                self.assertEqual(before,self.snapshot())
                response = self.claim() if operation=='claim' else self.renew(token)
                self.assertEqual(response.status_code,200)
                old = token if operation=='renew' else None
                token = response.json()['lease']['task_token']
                self.state(2 if operation=='claim' else 3,token)
                self.counts(1,0 if operation=='claim' else 1)
            del response
            self.stale(old)
            self.state(3,token)
