from tests.access_support import AccessFixtures
from tests.support import WorkpalCase
from tests.test_collaboration_updates import CollaborationUpdateFixtures

class CommentManagement(CollaborationUpdateFixtures, AccessFixtures, WorkpalCase):
    def test_update(self):
        self.prepare_notification()
        result = self.act(self.actor, 'comment.update', {'comment_id': self.comment['id'], 'body': 'edited'}, key='edit', revision=1)
        self.assertEqual(result.data['body'], 'edited')

    def edit(self, payload, key='edit', revision=1, actor=None):
        return self.act(actor or self.actor, 'comment.update', dict(comment_id=self.comment['id'], **payload), key=key, revision=revision)

    def test_cas(self):
        from workpal.contracts import DomainError
        self.prepare_notification()
        self.edit({'body':'first'})
        with self.assertRaises(DomainError) as caught: self.edit({'body':'second'},key='other')
        self.assertEqual(caught.exception.status,409)

    def test_omitted_mentions_and_clear(self):
        self.prepare_notification()
        self.assertEqual(self.edit({'body':'first'}).data['mentions'],[self.recipient.user_id])
        self.assertEqual(self.edit({'mention_user_ids':[]},key='clear',revision=2).data['mentions'],[])

    def test_identity_rejected(self):
        from workpal.contracts import DomainError
        self.prepare_notification()
        with self.assertRaises(DomainError): self.edit({'body':'x','author_user_id':self.recipient.user_id})

    def test_member_rejected(self):
        from workpal.contracts import DomainError
        self.prepare_notification()
        with self.assertRaises(DomainError) as caught: self.edit({'body':'x'},actor=self.recipient)
        self.assertEqual(caught.exception.status,403)

    def test_remove_restore(self):
        self.prepare_notification()
        payload={'comment_id':self.comment['id']}
        pending=self.act(self.actor,'comment.remove',payload,key='remove',revision=1)
        self.assertFalse(self.act(self.actor,'comment.read',payload).data['archived'])
        self.act(self.actor,'comment.remove',payload,key='remove',revision=1,confirmation_id=pending.data['confirmation_id'])
        self.assertEqual(self.act(self.actor,'comment.list',{'issue_id':self.task['id']}).data['items'],[])
        self.assertEqual(len(self.act(self.actor,'comment.list',{'issue_id':self.task['id'],'include_archived':True}).data['items']),1)
        restored=self.act(self.actor,'comment.restore',payload,key='restore',revision=2).data
        self.assertFalse(restored['archived'])
        self.assertEqual(restored['body'],'hello')

    def test_old_mentions_not_renotified(self):
        from workpal.collaboration.models import Notification
        self.prepare_notification()
        self.edit({'body':'edited'})
        self.assertEqual(Notification.objects.count(),1)

    def test_removed_old_member_does_not_block(self):
        from workpal.identity.models import Membership
        self.prepare_notification()
        Membership.objects.filter(user_id=self.recipient.user_id).delete()
        self.assertEqual(self.edit({'body':'edited'}).data['body'],'edited')

    def test_invalid_new_mention_rolls_back(self):
        from workpal.contracts import DomainError
        from workpal.collaboration.models import Comment
        self.prepare_notification()
        before=Comment.objects.values().get(pk=self.comment['id'])
        with self.assertRaises(DomainError): self.edit({'body':'edited','mention_user_ids':[999999]})
        self.assertEqual(Comment.objects.values().get(pk=self.comment['id']),before)

    def test_admin_demotion_and_source_write_replay(self):
        from workpal.identity.models import Membership
        from workpal.access.models import SourceGrant, RegisteredObject
        from workpal.collaboration import service
        from workpal.contracts import DomainError
        self.prepare_notification()
        membership=Membership.objects.get(user_id=self.recipient.user_id,workspace=self.workspace)
        membership.role='admin'; membership.save()
        self.edit({'body':'admin'},actor=self.recipient)
        membership.role='member'; membership.save()
        with self.assertRaises(DomainError) as caught: self.edit({'body':'admin'},actor=self.recipient)
        self.assertEqual(caught.exception.status,403)
        grant=self.grant(self.a,read=True,write=True)
        self.register(self.workspace.pk,service.ref(self.comment['id']),[self.a])
        self.edit({'body':'author'},key='author',revision=2)
        grant.write=False; grant.save()
        for key,revision in [('author',2),('fresh',3)]:
            with self.assertRaises(DomainError) as caught: self.edit({'body':'author'},key=key,revision=revision)
            self.assertEqual(caught.exception.status,403)

    def test_confirmation_revision_source_and_agent(self):
        from workpal.actions.models import Confirmation
        from workpal.collaboration import service
        from workpal.contracts import Actor, DomainError
        self.prepare_notification()
        p={'comment_id':self.comment['id']}
        pending=self.act(self.actor,'comment.remove',p,key='r',revision=1)
        token=pending.data['confirmation_id']
        agent=Actor(self.actor.user_id,self.workspace.pk,executor_id='agent')
        with self.assertRaises(DomainError) as caught: self.act(agent,'comment.remove',p,key='r',revision=1,confirmation_id=token)
        self.assertEqual(caught.exception.status,403)
        self.edit({'body':'new'})
        with self.assertRaises(DomainError) as caught: self.act(self.actor,'comment.remove',p,key='r',revision=1,confirmation_id=token)
        self.assertEqual(caught.exception.status,409)
        self.assertFalse(Confirmation.objects.get(pk=token).consumed)
        pending=self.act(self.actor,'comment.remove',p,key='s',revision=2)
        token=pending.data['confirmation_id']
        self.grant(self.a,read=True,write=True)
        self.register(self.workspace.pk,service.ref(self.comment['id']),[self.a])
        with self.assertRaises(DomainError) as caught: self.act(self.actor,'comment.remove',p,key='s',revision=2,confirmation_id=token)
        self.assertEqual(caught.exception.status,409)
        self.assertFalse(Confirmation.objects.get(pk=token).consumed)

    def test_source_append_restricts_old_notifications(self):
        from workpal.contracts import DomainError
        self.prepare_notification()
        self.grant(self.a,read=True,write=True)
        self.edit({'source_refs':[{'kind':self.a.kind,'id':self.a.id}]})
        self.assertEqual(self.act(self.recipient,'inbox.list',{}).data['items'],[])
        self.edit({'source_refs':[]},key='empty',revision=2)
        with self.assertRaises(DomainError): self.act(self.recipient,'comment.read',{'comment_id':self.comment['id']})

    def test_late_failure_rolls_back_all_tables_and_retry(self):
        from unittest.mock import patch
        from django.apps import apps
        from workpal.collaboration import service
        self.prepare_notification()
        user=__import__('django.contrib.auth',fromlist=['get_user_model']).get_user_model().objects.create(username='new')
        from workpal.identity.models import Membership
        Membership.objects.create(workspace=self.workspace,user=user,role='member')
        self.grant(self.a,read=True,write=True)
        models=list(apps.get_models())
        def snapshot(): return {m._meta.label:list(m.objects.order_by('pk').values()) for m in models}
        for target in ('comment','notification'):
            before=snapshot()
            original=service.register_object
            def broken(workspace,ref,sources=()):
                original(workspace,ref,sources)
                if ref.kind==target: raise RuntimeError('late failure')
            payload={'body':'new','mention_user_ids':[user.pk],'source_refs':[]}
            if target=='comment': payload['source_refs']=[{'kind':self.a.kind,'id':self.a.id}]
            with patch.object(service,'register_object',broken):
                with self.assertRaises(RuntimeError): self.edit(payload,key=target)
            self.assertEqual(snapshot(),before)
        self.edit({'body':'new','mention_user_ids':[user.pk]},key='notification')

    def test_archived_edit_conflict_and_completed_replay(self):
        from workpal.contracts import DomainError
        self.prepare_notification()
        edited=self.edit({'body':'retained'}).data
        p={'comment_id':self.comment['id']}
        pending=self.act(self.actor,'comment.remove',p,key='remove',revision=2)
        token=pending.data['confirmation_id']
        removed=self.act(self.actor,'comment.remove',p,key='remove',revision=2,confirmation_id=token).data
        self.assertTrue(removed['archived'])
        self.assertEqual(self.edit({'body':'retained'}).data,edited)
        with self.assertRaises(DomainError) as caught: self.edit({'body':'bad'},key='new',revision=3)
        self.assertEqual(caught.exception.status,409)
        self.assertEqual(self.act(self.actor,'comment.remove',p,key='remove',revision=2,confirmation_id=token).data,removed)

    def test_body_validation_and_create_still_requires_body(self):
        from workpal.contracts import DomainError
        self.prepare_notification()
        for body in ('   ','x'*20001,'\ud800'):
            with self.subTest(body_length=len(body)):
                with self.assertRaises(DomainError): self.edit({'body':body})
        with self.assertRaises(DomainError): self.act(self.actor,'comment.create',{'issue_id':self.task['id']},key='missing')

    def test_new_mention_once_no_subscriber_notification(self):
        from django.contrib.auth import get_user_model
        from workpal.identity.models import Membership
        from workpal.collaboration.models import Notification
        self.prepare_notification()
        users=[get_user_model().objects.create(username=name) for name in ('new','subscriber')]
        for user in users: Membership.objects.create(workspace=self.workspace,user=user,role='member')
        from workpal.contracts import Actor
        self.act(Actor(users[1].pk,self.workspace.pk),'issue.subscribe',{'issue_id':self.task['id']},key='sub')
        payload={'mention_user_ids':[self.recipient.user_id,users[0].pk,self.actor.user_id]}
        result=self.edit(payload)
        self.assertEqual(result.data,self.edit(payload).data)
        self.assertEqual(list(Notification.objects.order_by('pk').values_list('recipient_id',flat=True)),[self.recipient.user_id,users[0].pk])

from django.test import TransactionTestCase

class ConcurrentCommentManagement(CollaborationUpdateFixtures, AccessFixtures, TransactionTestCase):
    act=WorkpalCase.act

    def race(self,same_key):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from workpal.actions.registry import execute
        from workpal.contracts import ActionRequest, DomainError
        from django.contrib.auth import get_user_model
        from workpal.identity.models import Membership
        from workpal.collaboration.models import Notification
        self.prepare_notification()
        user=get_user_model().objects.create(username='new')
        Membership.objects.create(user=user,workspace=self.workspace,role='member')
        barrier=Barrier(2)
        def worker(index):
            connections.close_all()
            try:
                connection=connections['default']; connection.ensure_connection()
                self.assertNotEqual(connection.settings_dict['NAME'],':memory:')
                self.assertNotIn('mode=memory',str(connection.settings_dict['NAME']))
                identity=id(connection.connection)
                barrier.wait(timeout=10)
                try:
                    result=execute(self.actor,ActionRequest('comment.update',{'comment_id':self.comment['id'],'body':'edited','mention_user_ids':[user.pk]},1,'same' if same_key else str(index)))
                    return identity,result.data
                except DomainError as error: return identity,error.status
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(worker,range(2)))
        self.assertNotEqual(results[0][0],results[1][0])
        if same_key: self.assertEqual(results[0][1],results[1][1])
        else: self.assertEqual(sum(r[1]==409 for r in results),1)
        self.assertEqual(Notification.objects.filter(recipient=user).count(),1)

    def test_same_revision(self): self.race(False)
    def test_same_key(self): self.race(True)
