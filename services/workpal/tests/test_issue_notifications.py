from tests.support import WorkpalCase
from tests.access_support import AccessFixtures
from django.contrib.auth import get_user_model
from workpal.identity.models import Membership
from workpal.contracts import Actor

class IssueNotifications(AccessFixtures, WorkpalCase):
    def test_assignment_reaches_inbox(self):
        self.member.role='owner'; self.member.save()
        target=get_user_model().objects.create(username='recipient')
        Membership.objects.create(workspace=self.workspace,user=target,role='member')
        project=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        issue=self.act(self.actor,'issue.create',dict(project_id=project['id'],title='Task',assignee_user_id=target.pk),key='i').data
        inbox=self.act(Actor(target.pk,self.workspace.pk),'inbox.list',{}).data['items']
        self.assertEqual([(n['issue_id'],n['kind']) for n in inbox],[(issue['id'],'assignment')])

class HookContracts(AccessFixtures, __import__('django.test',fromlist=['TransactionTestCase']).TransactionTestCase):
    def setUp(self):
        super().setUp()
        from workpal.work import service, issues
        self.member.role='owner'; self.member.save()
        self.target=get_user_model().objects.create(username='recipient')
        Membership.objects.create(workspace=self.workspace,user=self.target,role='member')
        self.recipient=Actor(self.target.pk,self.workspace.pk)
        self.project=service.create(self.actor,name='p')
        self.issue=issues.create(self.actor,self.project['id'],'Task')

    def assign(self, uid):
        from workpal.work import issues
        self.issue=issues.update(self.actor,self.issue['id'],self.issue['revision'],assignee_user_id=uid)

    def count(self):
        from workpal.collaboration.models import Notification
        return Notification.objects.count()

    def test_changed_assignment(self):
        self.assign(self.target.pk); self.assertEqual(self.count(),1)
        self.assign(self.user.pk); self.assertEqual(self.count(),1)

    def test_same_and_clear(self):
        self.assign(self.target.pk); self.assign(self.target.pk); self.assign(0)
        self.assertEqual(self.count(),1)

    def test_human_self(self):
        self.assign(self.user.pk); self.assertEqual(self.count(),0)

    def test_duplicate_hook(self):
        from workpal.collaboration.service import notify_assignment
        self.assign(self.target.pk)
        notify_assignment(self.actor,self.issue['id'],self.issue['revision'])
        self.assertEqual(self.count(),1)

    def test_stale_hook(self):
        from workpal.collaboration.service import notify_assignment
        from workpal.contracts import DomainError
        self.assign(self.target.pk)
        with self.assertRaises(DomainError) as caught: notify_assignment(self.actor,self.issue['id'],1)
        self.assertEqual(caught.exception.status,409)

    def test_nonblocked_hook(self):
        from workpal.collaboration.service import notify_blocked
        from workpal.contracts import DomainError
        with self.assertRaises(DomainError) as caught: notify_blocked(self.actor,self.issue['id'],1)
        self.assertEqual(caught.exception.status,409)
        self.assertEqual(self.count(),0)

    def test_other_workspace(self):
        from workpal.collaboration.service import notify_assignment
        from workpal.contracts import DomainError
        Membership.objects.create(workspace=self.other,user=self.user,role='owner')
        with self.assertRaises(DomainError): notify_assignment(Actor(self.user.pk,self.other.pk),self.issue['id'],1)
        self.assertEqual(self.count(),0)

    def test_strict_ids(self):
        from workpal.collaboration.service import notify_assignment
        from workpal.contracts import DomainError
        for ident, revision in [(True,1),(1,True),('1',1),(1,0)]:
            with self.assertRaises(DomainError) as caught: notify_assignment(self.actor,ident,revision)
            self.assertEqual(caught.exception.status,400)

    def test_recipient_isolation(self):
        from workpal.collaboration import service
        from workpal.contracts import DomainError
        self.assign(self.target.pk)
        notification=service.listing(self.recipient)['items'][0]
        self.assertEqual(service.listing(self.actor)['items'],[])
        with self.assertRaises(DomainError) as caught: service.mark_read(self.actor,notification['id'],1)
        self.assertEqual(caught.exception.status,404)

    def test_blocked_self_and_release(self):
        from workpal.work import transitions
        from workpal.collaboration import service
        definition=self.issue['workflow_snapshot']['definition']
        current=self.issue['status_key']
        # Follow real snapshot edges to blocked.
        blocked=next(s['key'] for s in definition['states'] if s['category']=='blocked')
        edges=definition['transitions']
        path=[current]; queue=[path]
        while queue:
            path=queue.pop(0)
            if path[-1]==blocked: break
            queue.extend(path+[e['to']] for e in edges if e['from']==path[-1] and e['to'] not in path)
        for target in path[1:]:
            self.issue=transitions.transition(self.actor,self.issue['id'],target,self.issue['revision'],reason='Decision',blocked_owner_user_id=self.user.pk if target==blocked else 0)
        inbox=service.listing(self.actor)['items']
        self.assertEqual([n['kind'] for n in inbox],['blocked'])
        target=next(e['to'] for e in edges if e['from']==blocked)
        transitions.transition(self.actor,self.issue['id'],target,self.issue['revision'],reason='Resolved')
        self.assertEqual(service.listing(self.actor)['items'],inbox)

    def test_assignment_registration_failure_rolls_back(self):
        from unittest.mock import patch
        from django.apps import apps
        from workpal.collaboration import service
        from workpal.contracts import DomainError
        from workpal.work import issues
        models=[m for m in apps.get_models() if m._meta.app_label in ('work','collaboration','access','actions','audit')]
        def snapshot(): return {m._meta.label:list(m.objects.order_by('pk').values()) for m in models}
        before=snapshot(); original=service.register_object
        def broken(*args,**kwargs):
            original(*args,**kwargs)
            raise DomainError('unavailable','Unavailable.',status=503)
        with patch.object(service,'register_object',side_effect=broken):
            with self.assertRaises(DomainError) as caught: self.assign(self.target.pk)
        self.assertEqual(caught.exception.status,503)
        self.assertEqual(snapshot(),before)
        self.assign(self.target.pk)
        self.assertEqual(self.count(),1)
