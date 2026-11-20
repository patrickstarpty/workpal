from tests.support import WorkpalCase
from tests.access_support import AccessFixtures

class Issues(AccessFixtures, WorkpalCase):
    def test_create(self):
        self.member.role='owner'; self.member.save()
        p=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        self.member.role='member'; self.member.save()
        result=self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'Task'},key='i').data
        self.assertEqual(result['title'],'Task')
        self.assertEqual(result['status_key'],'backlog')

    def issue(self):
        self.member.role='owner'; self.member.save()
        p=self.act(self.actor,'project.create',{'name':'same'},key='p').data
        self.member.role='member'; self.member.save()
        return self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'Task','description':'old'},key='i').data

    def test_history_and_clearing(self):
        a=self.issue()
        b=self.act(self.actor,'issue.update',{'issue_id':a['id'],'title':'New'},key='u',revision=1).data
        self.assertEqual(b['description'],'old')
        self.assertEqual(b['requirements_revision'],2)
        old=self.act(self.actor,'issue.requirements.read',{'issue_id':a['id'],'number':1}).data
        self.assertEqual(old['title'],'Task')
        c=self.act(self.actor,'issue.update',{'issue_id':a['id'],'description':'','criteria':[]},key='clear',revision=2).data
        self.assertEqual(c['description'],'')
        self.assertEqual(old,self.act(self.actor,'issue.requirements.read',{'issue_id':a['id'],'number':1}).data)

    def test_replay_and_equal_content(self):
        from workpal.work.models import Issue, IssueRequirements
        from workpal.contracts import DomainError
        a=self.issue()
        payload={'issue_id':a['id'],'title':'Task'}
        b=self.act(self.actor,'issue.update',payload,key='u',revision=1).data
        self.assertEqual(b['requirements_revision'],1)
        self.assertEqual(b,self.act(self.actor,'issue.update',payload,key='u',revision=1).data)
        with self.assertRaises(DomainError): self.act(self.actor,'issue.update',{**payload,'title':'different'},key='u',revision=1)
        self.assertEqual(Issue.objects.count(),1); self.assertEqual(IssueRequirements.objects.count(),1)

    def test_direct_readonly_and_cas(self):
        from workpal.work import issues
        from workpal.contracts import DomainError
        a=self.issue()
        for fields in ({'status_key':'done'},{'project_id':a['project_id']},{'revision':5},{'workflow_snapshot':{}},{}):
            with self.assertRaises((DomainError,TypeError)): issues.update(self.actor,a['id'],1,**fields)
        with self.assertRaises(DomainError) as e: issues.update(self.actor,a['id'],2,title='bad')
        self.assertEqual(e.exception.status,409)

    def test_archive_preserves_history(self):
        a=self.issue()
        b=self.act(self.actor,'issue.archive',{'issue_id':a['id']},key='a',revision=1).data
        self.assertTrue(b['archived'])
        c=self.act(self.actor,'issue.restore',{'issue_id':a['id']},key='r',revision=2).data
        self.assertFalse(c['archived']); self.assertEqual(c['requirements_version_id'],a['requirements_version_id'])

    def test_late_failure_rolls_back(self):
        from unittest.mock import patch
        from workpal.work import issues
        from workpal.work.models import IssueRequirements
        a=self.issue()
        original=issues.register_object
        def broken(workspace,ref,sources=()):
            original(workspace,ref,sources)
            if ref.kind=='issue_requirements': raise RuntimeError('late failure')
        with patch.object(issues,'register_object',broken):
            with self.assertRaises(RuntimeError): self.act(self.actor,'issue.update',{'issue_id':a['id'],'title':'bad'},key='broken',revision=1)
        self.assertEqual(issues.read(self.actor,a['id']),a)
        self.assertEqual(IssueRequirements.objects.count(),1)

    def test_revocation_and_visible_pagination(self):
        from workpal.work import issues
        from workpal.contracts import DomainError
        a=self.issue()
        grant=self.grant(self.a,read=True,write=True)
        self.register(self.workspace.pk,issues.ref(a['id']),[self.a])
        b=issues.create(self.actor,a['project_id'],'visible')
        grant.read=False; grant.save()
        for call in (lambda:issues.read(self.actor,a['id']),lambda:issues.read_requirements(self.actor,a['id'],1),lambda:self.act(self.actor,'issue.create',{'project_id':a['project_id'],'title':'Task','description':'old'},key='i')):
            with self.assertRaises(DomainError): call()
        page=issues.list_issues(self.actor,limit=1)
        self.assertEqual([x['id'] for x in page['items']],[b['id']]); self.assertNotIn('total',page)

    def test_builtin_snapshot_is_independent(self):
        from unittest.mock import patch
        from workpal.work import issues
        a=self.issue()
        self.assertEqual(a['workflow_snapshot']['origin'],'builtin')
        self.assertEqual(a['workflow_snapshot']['version_id'],0)
        with patch('workpal.workflows.service.builtin_snapshot',return_value={}):
            self.assertEqual(issues.read(self.actor,a['id'])['workflow_snapshot'],a['workflow_snapshot'])
        a['workflow_snapshot']['definition']['states'].clear()
        self.assertTrue(issues.read(self.actor,a['id'])['workflow_snapshot']['definition']['states'])

from django.test import TransactionTestCase
class ConcurrentIssues(AccessFixtures,TransactionTestCase):
    def test_two_connections_one_requirements_append(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from workpal.actions.registry import execute
        from workpal.contracts import ActionRequest, DomainError
        from workpal.work.models import IssueRequirements
        self.member.role='owner'; self.member.save()
        p=execute(self.actor,ActionRequest('project.create',{'name':'p'},None,'p')).data
        i=execute(self.actor,ActionRequest('issue.create',{'project_id':p['id'],'title':'before'},None,'i')).data
        barrier=Barrier(2)
        def update(key):
            connections.close_all()
            try:
                connection=connections['default']; connection.ensure_connection(); identity=id(connection.connection)
                barrier.wait(timeout=10)
                try:
                    execute(self.actor,ActionRequest('issue.update',{'issue_id':i['id'],'title':key},1,key))
                    return identity,'completed'
                except DomainError as e: return identity,e.status
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(update,['one','two']))
        self.assertEqual(len({r[0] for r in results}),2)
        self.assertCountEqual([r[1] for r in results],['completed',409])
        self.assertEqual(IssueRequirements.objects.count(),2)
