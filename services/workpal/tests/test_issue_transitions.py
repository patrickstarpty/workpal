from tests.support import WorkpalCase
from tests.access_support import AccessFixtures

class Transitions(AccessFixtures, WorkpalCase):
    def test_transition_records_fact(self):
        self.member.role='owner'; self.member.save()
        p=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        i=self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'Task'},key='i').data
        result=self.act(self.actor,'issue.transition',{'issue_id':i['id'],'target':'todo'},key='t',revision=1).data
        self.assertEqual(result['status_key'],'todo')
        self.assertEqual(result['requirements_version_id'],i['requirements_version_id'])

    def test_cas_illegal_and_block_validation(self):
        from workpal.contracts import DomainError
        from workpal.work.models import IssueTransition
        self.member.role='owner'; self.member.save()
        p=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        i=self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'Task'},key='i').data
        for payload,rev in [({'target':'done'},1),({'target':'todo'},2),({'target':'blocked'},1)]:
            with self.assertRaises(DomainError): self.act(self.actor,'issue.transition',dict(issue_id=i['id'],**payload),key=str(payload)+str(rev),revision=rev)
        self.assertFalse(IssueTransition.objects.exists())

    def test_late_history_failure_rolls_back(self):
        from unittest.mock import patch
        from workpal.work import transitions, issues
        from workpal.work.models import IssueTransition
        self.member.role='owner'; self.member.save()
        p=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        i=self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'Task'},key='i').data
        with patch.object(transitions,'register_object',side_effect=RuntimeError('late')):
            with self.assertRaises(RuntimeError): self.act(self.actor,'issue.transition',{'issue_id':i['id'],'target':'todo'},key='t',revision=1)
        self.assertEqual(issues.read(self.actor,i['id']),i)
        self.assertFalse(IssueTransition.objects.exists())
        self.act(self.actor,'issue.transition',{'issue_id':i['id'],'target':'todo'},key='t',revision=1)

from django.test import TransactionTestCase
from django.db import connections
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from workpal.actions.registry import execute
from workpal.contracts import ActionRequest, DomainError

class ConcurrentTransitions(AccessFixtures, TransactionTestCase):
    def test_same_revision_one_winner(self):
        self.member.role='owner'; self.member.save()
        from workpal.work import issues, service
        p=execute(self.actor,ActionRequest('project.create',{'name':'p'},None,'p')).data
        i=issues.create(self.actor,p['id'],'Task')
        barrier=Barrier(2)
        def run(key):
            connections.close_all()
            try:
                connections['default'].ensure_connection()
                identity=id(connections['default'].connection)
                barrier.wait(timeout=10)
                try:
                    execute(self.actor,ActionRequest('issue.transition',{'issue_id':i['id'],'target':'todo'},1,key))
                    return identity,'completed'
                except DomainError as e: return identity,e.code
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(run,['a','b']))
        self.assertEqual(len({r[0] for r in results}),2)
        self.assertCountEqual([r[1] for r in results],['completed','revision_conflict'])
