from tests.support import WorkpalCase
from tests.access_support import AccessFixtures

class Collaboration(AccessFixtures, WorkpalCase):
    def issue(self):
        self.member.role='owner'; self.member.save()
        project=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        self.member.role='member'; self.member.save()
        return self.act(self.actor,'issue.create',{'project_id':project['id'],'title':'Task'},key='i').data
    def test_member_comment_text(self):
        issue=self.issue()
        text='<img onerror=alert(1)>'
        result=self.act(self.actor,'comment.create',dict(issue_id=issue['id'],body=text),key='comment')
        self.assertEqual(result.data['body'],text)

    def prepare(self):
        from django.contrib.auth import get_user_model
        from workpal.identity.models import Membership
        from workpal.contracts import Actor
        self.target=get_user_model().objects.create(username='target')
        self.target_member=Membership.objects.create(workspace=self.workspace,user=self.target,role='member')
        self.recipient=Actor(self.target.pk,self.workspace.pk)
        self.task=self.issue()
        self.act(self.recipient,'issue.subscribe',{'issue_id':self.task['id']},key='sub')
        return dict(issue_id=self.task['id'],body='hello')

    def test_replay_conflict_and_events(self):
        from workpal.collaboration.models import Comment,Notification
        from workpal.audit.models import Outbox
        from workpal.contracts import DomainError
        p=self.prepare()
        first=self.act(self.actor,'comment.create',p,key='c').data
        self.assertEqual(first,self.act(self.actor,'comment.create',p,key='c').data)
        with self.assertRaises(DomainError) as e: self.act(self.actor,'comment.create',{**p,'body':'other'},key='c')
        self.assertEqual(e.exception.status,409)
        self.assertEqual((Comment.objects.count(),Notification.objects.count()),(1,1))
        self.assertEqual(Outbox.objects.filter(action_id='comment.create').count(),1)

    def test_dedup_self_and_unsubscribe(self):
        from workpal.collaboration.models import Notification
        p=self.prepare()
        self.act(self.actor,'issue.subscribe',{'issue_id':self.task['id']},key='self')
        self.act(self.actor,'comment.create',{**p,'mention_user_ids':[self.target.pk,self.user.pk]},key='c')
        self.assertEqual(list(Notification.objects.values_list('recipient_id','kind')),[(self.target.pk,'mention')])
        self.act(self.recipient,'issue.unsubscribe',{'issue_id':self.task['id']},key='unsub')
        self.act(self.actor,'comment.create',p,key='c2')
        self.assertEqual(Notification.objects.count(),1)

    def restricted(self):
        p=self.prepare()
        self.grant(self.a,read=True,write=True)
        return {**p,'source_refs':[dict(kind=self.a.kind,id=self.a.id)]}

    def test_restricted_subscriber_skipped(self):
        from workpal.collaboration.models import Notification
        p=self.restricted()
        self.act(self.actor,'comment.create',p,key='c')
        self.assertEqual(Notification.objects.count(),0)

    def test_invalid_explicit_mention_rolls_back(self):
        from workpal.collaboration.models import Comment,Notification
        from workpal.contracts import DomainError
        p=self.restricted()
        with self.assertRaises(DomainError): self.act(self.actor,'comment.create',{**p,'mention_user_ids':[self.target.pk]},key='c')
        self.assertEqual((Comment.objects.count(),Notification.objects.count()),(0,0))

    def grant_target(self):
        from workpal.access.models import SourceGrant,RegisteredObject
        return SourceGrant.objects.create(user=self.target,source=RegisteredObject.objects.get(kind=self.a.kind,object_id=self.a.id),read=True)

    def test_revocation_hides_and_blocks_replay(self):
        from workpal.contracts import DomainError
        p=self.restricted(); grant=self.grant_target()
        c=self.act(self.actor,'comment.create',{**p,'mention_user_ids':[self.target.pk]},key='c').data
        n=self.act(self.recipient,'inbox.list',{}).data['items'][0]
        self.act(self.recipient,'inbox.mark_read',{'notification_id':n['id']},key='read',revision=1)
        grant.delete()
        self.assertEqual(self.act(self.recipient,'inbox.list',{}).data,dict(items=[],next_cursor=0))
        self.assertEqual(self.act(self.recipient,'comment.list',{'issue_id':p['issue_id']}).data,dict(items=[],next_cursor=0))
        for action,payload,key,rev in [('comment.read',{'comment_id':c['id']},None,None),('inbox.mark_read',{'notification_id':n['id']},'read',1)]:
            with self.assertRaises(DomainError): self.act(self.recipient,action,payload,key=key,revision=rev)

    def test_readonly_mark_read_cas_no_issue_effect(self):
        from workpal.work import issues
        from workpal.contracts import DomainError
        p=self.restricted(); self.grant_target()
        before=issues.read(self.actor,p['issue_id'])
        self.act(self.actor,'comment.create',p,key='c')
        n=self.act(self.recipient,'inbox.list',{}).data['items'][0]
        self.assertEqual(n['read_at'],'')
        again=self.act(self.recipient,'inbox.list',{}).data['items'][0]
        self.assertEqual(n,again)
        marked=self.act(self.recipient,'inbox.mark_read',{'notification_id':n['id']},key='read',revision=1).data
        self.assertEqual(marked['revision'],2)
        self.assertEqual(marked,self.act(self.recipient,'inbox.mark_read',{'notification_id':n['id']},key='read',revision=1).data)
        with self.assertRaises(DomainError): self.act(self.recipient,'inbox.mark_read',{'notification_id':n['id']},key='stale',revision=1)
        self.assertEqual(before,issues.read(self.actor,p['issue_id']))

    def test_owner_cannot_mark_other_recipient(self):
        from workpal.contracts import DomainError
        p=self.prepare(); self.act(self.actor,'comment.create',p,key='c')
        n=self.act(self.recipient,'inbox.list',{}).data['items'][0]
        self.member.role='owner';self.member.save()
        with self.assertRaises(DomainError) as e: self.act(self.actor,'inbox.mark_read',{'notification_id':n['id']},key='r',revision=1)
        self.assertEqual(e.exception.status,404)

    def test_authorized_pagination(self):
        p=self.restricted()
        self.act(self.actor,'comment.create',p,key='hidden')
        visible=[]
        for number in range(3):
            visible.append(self.act(self.actor,'comment.create',{'issue_id':p['issue_id'],'body':str(number)},key=str(number)).data['id'])
        page=self.act(self.recipient,'comment.list',{'issue_id':p['issue_id'],'limit':2}).data
        self.assertEqual([x['id'] for x in page['items']],visible[:2])
        self.assertEqual(page['next_cursor'],visible[1])
        inbox=self.act(self.recipient,'inbox.list',{'limit':2}).data
        self.assertEqual([x['comment_id'] for x in inbox['items']],visible[:2])
        self.assertEqual(set(inbox),{'items','next_cursor'})

    def test_invalid_inputs_and_archived(self):
        from workpal.contracts import DomainError
        from workpal.collaboration import service
        p=self.prepare()
        for changes in ({'body':' '},{'body':'\ud800'},{'mention_user_ids':[True]},{'mention_user_ids':[1,1]},{'issue_id':True},{'user_id':1},{'mention_user_ids':[-1]},{'body':'x'*20001}):
            with self.assertRaises((DomainError,TypeError)): self.act(self.actor,'comment.create',{**p,**changes},key='bad')
            with self.assertRaises((DomainError,TypeError)): service.create(self.actor,**{**p,**changes})
        self.act(self.actor,'issue.archive',{'issue_id':p['issue_id']},key='archive',revision=1)
        with self.assertRaises(DomainError) as e: self.act(self.actor,'comment.create',p,key='archived')
        self.assertEqual(e.exception.status,409)

    def test_removed_inactive_and_cross_workspace(self):
        from workpal.contracts import DomainError,Actor
        from workpal.collaboration.models import Comment
        p=self.prepare()
        for recipient in (Actor(self.target.pk,self.other.pk),):
            with self.assertRaises(DomainError): self.act(recipient,'comment.create',p,key='bad')
        self.target.is_active=False; self.target.save()
        with self.assertRaises(DomainError): self.act(self.actor,'comment.create',{**p,'mention_user_ids':[self.target.pk]},key='bad')
        self.target.is_active=True;self.target.save();self.target_member.delete()
        with self.assertRaises(DomainError): self.act(self.recipient,'issue.unsubscribe',{'issue_id':p['issue_id']},key='unsub')
        self.register(self.other.pk,__import__('workpal.contracts',fromlist=['ObjectRef']).ObjectRef('source','foreign'),is_source=True)
        with self.assertRaises(DomainError): self.act(self.actor,'comment.create',{**p,'source_refs':[dict(kind='source',id='foreign')]},key='cross')
        self.assertEqual(Comment.objects.count(),0)

    def test_late_registration_failure_rolls_back_and_retries(self):
        from unittest.mock import patch
        from workpal.collaboration import service
        from workpal.collaboration.models import Comment,Notification,Subscription
        from workpal.access.models import RegisteredObject,SourceLink
        from workpal.actions.models import IdempotencyResult
        from workpal.audit.models import AuditEvent,Outbox
        p=self.prepare()
        models=(Comment,Notification,Subscription,RegisteredObject,SourceLink,IdempotencyResult,AuditEvent,Outbox)
        before=[m.objects.count() for m in models]
        original=service.register_object
        def broken(workspace,ref,sources=()):
            original(workspace,ref,sources)
            if ref.kind=='notification': raise RuntimeError('late failure')
        with patch.object(service,'register_object',broken):
            with self.assertRaises(RuntimeError): self.act(self.actor,'comment.create',p,key='retry')
        self.assertEqual([m.objects.count() for m in models],before)
        self.act(self.actor,'comment.create',p,key='retry')
        self.assertEqual((Comment.objects.count(),Notification.objects.count()),(1,1))

from django.test import TransactionTestCase

class ConcurrentCollaboration(AccessFixtures, TransactionTestCase):
    issue=Collaboration.issue
    prepare=Collaboration.prepare
    from tests.support import WorkpalCase as _Case
    act=_Case.act
    del _Case

    def test_two_connections_same_key(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from workpal.actions.registry import execute
        from workpal.contracts import ActionRequest
        from workpal.collaboration.models import Comment,Notification
        from workpal.audit.models import Outbox,AuditEvent
        payload=self.prepare()
        barrier=Barrier(2)
        def worker(_):
            connections.close_all()
            try:
                conn=connections['default'];conn.ensure_connection()
                identity=id(conn.connection)
                barrier.wait(timeout=10)
                result=execute(self.actor,ActionRequest('comment.create',payload,None,'same'))
                return identity,result.data
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(worker,range(2)))
        self.assertNotEqual(results[0][0],results[1][0])
        self.assertEqual(results[0][1],results[1][1])
        self.assertEqual((Comment.objects.count(),Notification.objects.count()),(1,1))
        self.assertEqual(Outbox.objects.filter(action_id='comment.create').count(),1)
        self.assertEqual(AuditEvent.objects.filter(action_id='comment.create').count(),1)
