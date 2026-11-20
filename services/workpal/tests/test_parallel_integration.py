"""Default composition exercised through authenticated HTTP."""
from django.test import TransactionTestCase, Client, override_settings
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership
from workpal.contracts import Actor
from workpal.work import service as projects, issues

@override_settings(ALLOWED_HOSTS=['testserver'])
class ParallelIntegration(TransactionTestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='integration',password='integration-password')
        self.workspace=Workspace.objects.create(name='Integration')
        Membership.objects.create(user=self.user,workspace=self.workspace,role='owner')
        self.actor=Actor(self.user.pk,self.workspace.pk)
        self.project=projects.create(self.actor,'Project')['id']
        self.issue=issues.create(self.actor,self.project,'Task')
        self.client=Client(enforce_csrf_checks=True)
        token=self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.assertEqual(self.client.post('/api/v1/auth/login',dict(username='integration',password='integration-password'),content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code,200)
    def call(self,action,payload,revision=None,headers=True):
        return self.client.post('/api/v1/actions/'+action,dict(workspace_id=self.workspace.pk,payload=payload,idempotency_key=action,expected_revision=revision),content_type='application/json',**({'HTTP_X_CSRFTOKEN':self.client.cookies['csrftoken'].value} if headers else {}))
    def data(self,action,payload,revision=None):
        response=self.call(action,payload,revision)
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['state'],'completed',response.content)
        return response.json()['data']
    def test_default_http_agent_run_and_environment_records(self):
        agent=self.data('agent.create',dict(name='Builder'))
        run=self.data('run.start',dict(subject=dict(type='issue',id=self.issue['id']),agent_id=agent['id'],key='start'))
        self.assertEqual(run['status'],'deferred')
        self.assertEqual(run['deferred_reason']['code'],'runtime_unavailable')
        self.assertEqual(self.data('run.read',dict(run_id=run['id'])),run)
        self.assertEqual(self.data('run.cancel',dict(run_id=run['id']),1)['status'],'cancelled')
        self.assertEqual(issues.read(self.actor,self.issue['id']),self.issue)
        env=self.data('environment.create',dict(project_id=self.project,name='SIT',timezone='UTC'))
        svc=self.data('environment_service.create',dict(environment_id=env['id'],name='web'))
        self.assertEqual(self.data('environment.read',dict(environment_id=env['id'])),env)
        self.assertIn(env,self.data('environment.list',dict(project_id=self.project))['items'])
        self.assertEqual(self.data('environment_service.read',dict(service_id=svc['id'])),svc)
        self.assertIn(svc,self.data('environment_service.list',dict(environment_id=env['id']))['items'])
        source=self.data('evidence_source.create_upload',dict(environment_id=env['id'],name='upload',allowed_services=[svc['id']]))
        self.assertEqual(self.data('evidence_source.read',dict(source_id=source['id'])),source)
        inv=self.data('investigation.start',dict(project_id=self.project,environment_id=env['id'],service_id=svc['id'],problem='Investigate',key='investigate'))
        self.assertEqual(self.data('investigation.read',dict(investigation_id=inv['id'])),inv)
        self.assertEqual(self.data('investigation.list',dict(project_id=self.project,environment_id=env['id']))['items'],[inv])
    def test_default_http_authorization_and_registration(self):
        from django.apps import apps
        labels=[a.label for a in apps.get_app_configs()]
        self.assertEqual(len(labels),len(set(labels)))
        self.assertEqual(self.call('agent.create',dict(name='Missing CSRF'),headers=False).status_code,403)
        self.assertEqual(Client(enforce_csrf_checks=True).post('/api/v1/actions/agent.create',{},content_type='application/json').status_code,403)
        catalog=self.client.get('/api/v1/actions',dict(workspace_id=self.workspace.pk)).json()['actions']
        ids=[a['action_id'] for a in catalog]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(self.client.post('/api/v1/actions/agent.create',{},content_type='application/json',HTTP_HOST='invalid.example',HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value).status_code,400)
        agent=self.data('agent.create',dict(name='Builder'))
        env=self.data('environment.create',dict(project_id=self.project,name='SIT',timezone='UTC'))
        svc=self.data('environment_service.create',dict(environment_id=env['id'],name='web'))
        inv=self.data('investigation.start',dict(project_id=self.project,environment_id=env['id'],service_id=svc['id'],problem='Private',key='private'))
        membership=Membership.objects.get(user=self.user,workspace=self.workspace)
        membership.role='member'; membership.save()
        self.data('agent.read',dict(agent_id=agent['id']))
        self.assertEqual(self.call('agent.create',dict(name='Denied')).status_code,403)
        other=get_user_model().objects.create_user(username='member',password='member-password')
        Membership.objects.create(user=other,workspace=self.workspace,role='member')
        token=self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.assertEqual(self.client.post('/api/v1/auth/login',dict(username='member',password='member-password'),content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code,200)
        self.assertEqual(self.call('environment.read',dict(environment_id=env['id'])).status_code,403)
        self.assertEqual(self.call('investigation.read',dict(investigation_id=inv['id'])).status_code,403)
        self.assertEqual(self.call('environment.create',dict(project_id=self.project,name='Denied',timezone='UTC')).status_code,403)

    def test_existing_database_upgrade_preserves_issue(self):
        import os, subprocess, sys, tempfile
        from pathlib import Path
        script = '''
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership
from workpal.contracts import Actor
from workpal.access.models import SourceLink
from workpal.work import service, issues
from workpal.work.models import IssueRequirements
executor=MigrationExecutor(connection)
leaves=executor.loader.graph.leaf_nodes()
old=[target for target in leaves if target[0] not in ('agents','execution','investigation')]
executor.migrate(old)
u=get_user_model().objects.create_user(username='upgrade')
w=Workspace.objects.create(name='upgrade')
Membership.objects.create(user=u,workspace=w,role='owner')
a=Actor(u.pk,w.pk)
p=service.create(a,'Project')
i=issues.create(a,p['id'],'Preserved',criteria=[dict(key='ac1',text='criterion')],source_refs=[dict(kind='project',id=str(p['id']))])
before=IssueRequirements.objects.get(pk=i['requirements_version_id'])
fields={f.attname:getattr(before,f.attname) for f in before._meta.fields}
links=list(SourceLink.objects.order_by('pk').values_list('derived_id','source_id'))
MigrationExecutor(connection).migrate(leaves)
assert issues.read(a,i['id'])==i
assert list(SourceLink.objects.order_by('pk').values_list('derived_id','source_id'))==links
assert {f.attname:getattr(IssueRequirements.objects.get(pk=before.pk),f.attname) for f in before._meta.fields}==fields
from workpal.agents import service as agents
from workpal.execution import service as runs
agent=agents.create(a,'Builder')
assert runs.start(a,dict(type='issue',id=i['id']),agent['id'],'upgrade')['status']=='deferred'
connection.close()
'''
        with tempfile.TemporaryDirectory(prefix='workpal-i1-upgrade-') as directory:
            env={**os.environ,'WORKPAL_DB_PATH':str(Path(directory)/'upgrade.sqlite3'),'DJANGO_SETTINGS_MODULE':'config.settings'}
            result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            env['WORKPAL_DB_PATH']=str(Path(directory)/'empty.sqlite3')
            result=subprocess.run([sys.executable,'manage.py','migrate','--noinput'],cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
