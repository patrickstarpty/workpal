import json
from django.test import Client
from tests.support import WorkpalCase
from tests.access_support import AccessFixtures

class IssueAliases(AccessFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.member.role='owner'; self.member.save()
        self.project=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        self.client=Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.token=self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.url=f'/api/v1/workspaces/{self.workspace.pk}/issues'
        self.payload={'project_id':self.project['id'],'title':'Task'}
    def post(self, payload=None, **headers):
        headers.setdefault('HTTP_X_CSRFTOKEN',self.token)
        headers.setdefault('HTTP_IDEMPOTENCY_KEY','i')
        return self.client.post(self.url,json.dumps(self.payload if payload is None else payload),content_type='application/json',**headers)
    def test_create(self):
        response=self.post()
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['title'],'Task')
    def test_replay(self):
        first=self.post()
        response=self.client.post('/api/v1/actions/issue.create',json.dumps({'workspace_id':self.workspace.pk,'payload':self.payload,'idempotency_key':'i'}),content_type='application/json',HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['data'],first.json())
    def test_conflict(self):
        self.assertEqual(self.post().status_code,200)
        self.assertEqual(self.post({**self.payload,'title':'Changed'}).status_code,409)
    def test_missing_key(self):
        self.assertEqual(self.post(HTTP_IDEMPOTENCY_KEY='').status_code,400)
    def test_host(self):
        self.assertEqual(self.post(HTTP_HOST='evil.invalid').status_code,400)
    def test_csrf(self):
        self.assertEqual(self.post(HTTP_X_CSRFTOKEN='').status_code,403)
    def test_anonymous(self):
        self.client.logout()
        self.assertEqual(self.post().status_code,403)
    def test_method(self):
        self.assertEqual(self.client.get(self.url).status_code,405)
    def test_identity_and_transport_fields(self):
        for field in ('workspace_id','revision','user_id','executor_id','status_key'):
            self.assertEqual(self.post({**self.payload,field:1}).status_code,400)
    def test_json(self):
        for raw in ('[]','{','{"title":NaN}','{"title":"a","title":"b"}','{"title":"\\ud800"}'):
            response=self.client.post(self.url,raw,content_type='application/json',HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY='i')
            self.assertEqual(response.status_code,400)
    def test_revoked_membership(self):
        self.assertEqual(self.post().status_code,200)
        self.member.delete()
        self.assertEqual(self.post().status_code,404)
    def test_transition_replay_and_stale(self):
        issue=self.post().json()
        url=f"/api/v1/issues/{issue['id']}/transitions"
        body={'workspace_id':self.workspace.pk,'revision':1,'target':'todo'}
        def transition(value, key):
            return self.client.post(url,json.dumps(value),content_type='application/json',HTTP_X_CSRFTOKEN=self.token,HTTP_IDEMPOTENCY_KEY=key)
        response=transition(body,'t')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['revision'],2)
        generic=self.client.post('/api/v1/actions/issue.transition',json.dumps({'workspace_id':self.workspace.pk,'payload':{'issue_id':issue['id'],'target':'todo'},'expected_revision':1,'idempotency_key':'t'}),content_type='application/json',HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(generic.json()['data'],response.json())
        self.assertEqual(transition({**body,'target':'in_progress'},'stale').status_code,409)
        for field,value in [('issue_id',issue['id']),('revision',True),('revision',2**63),('workspace_id',0),('executor_id','fake')]:
            self.assertEqual(transition({**body,field:value},'bad').status_code,400)
    def test_late_failure_retry(self):
        from unittest.mock import patch
        from workpal.work import issues
        from workpal.work.models import Issue
        original=issues.register_object
        def broken(workspace,ref,sources=()):
            original(workspace,ref,sources)
            if ref.kind=='issue_requirements':
                raise RuntimeError('private failure')
        with patch.object(issues,'register_object',broken):
            response=self.post()
        self.assertEqual(response.status_code,500)
        self.assertNotIn(b'private failure',response.content)
        self.assertFalse(Issue.objects.exists())
        self.assertEqual(self.post().status_code,200)
