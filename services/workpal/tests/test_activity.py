from tests.support import WorkpalCase
from tests.access_support import AccessFixtures

class Activity(AccessFixtures, WorkpalCase):
    def test_registry_activity(self):
        self.member.role='owner'; self.member.save()
        p=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        issue=self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'a'},key='a').data
        page=self.act(self.actor,'issue.activity.list',{'issue_id':issue['id']}).data
        self.assertEqual([x['action_id'] for x in page['items']],['issue.create'])

    def setup_issue(self):
        self.member.role='owner'; self.member.save()
        p=self.act(self.actor,'project.create',{'name':'p'},key='p').data
        self.issue=self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'a'},key='a').data
        return p

    def page(self, **kwargs):
        return self.act(self.actor,'issue.activity.list',dict(issue_id=self.issue['id'],**kwargs))

    def test_reads_excluded(self):
        from workpal.audit.models import Outbox
        self.setup_issue(); before=Outbox.objects.count()
        self.act(self.actor,'issue.read',{'issue_id':self.issue['id']})
        self.assertEqual(self.page().data,self.page().data)
        self.assertEqual(len(self.page().data['items']),1)
        self.assertEqual(Outbox.objects.count(),before)

    def test_replay(self):
        p=self.setup_issue()
        self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'a'},key='a')
        self.assertEqual(len(self.page().data['items']),1)

    def test_parent_not_subject(self):
        p=self.setup_issue()
        self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'child','parent_issue_id':self.issue['id']},key='child')
        self.assertEqual(len(self.page().data['items']),1)

    def test_comment_source_not_subject(self):
        p=self.setup_issue()
        other=self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'other'},key='other').data
        self.act(self.actor,'comment.create',{'issue_id':other['id'],'body':'private','source_refs':[{'kind':'issue','id':str(self.issue['id'])}]},key='comment')
        self.assertEqual(len(self.page().data['items']),1)
        page=self.act(self.actor,'issue.activity.list',{'issue_id':other['id']}).data
        self.assertEqual([x['action_id'] for x in page['items']],['issue.create','comment.create'])

    def test_closed_projection(self):
        self.setup_issue()
        item=self.page().data['items'][0]
        self.assertEqual(set(item),{'id','action_id','actor_user_id','created_at','object_refs'})
        self.assertEqual(set(self.page().data),{'items','next_cursor'})

    def test_direct_invalid(self):
        from workpal.audit.activity import list_issue_activity
        from workpal.contracts import DomainError
        self.setup_issue()
        for values in ({'issue_id':True},{'issue_id':0},{'limit':True},{'limit':201},{'cursor':None},{'cursor':'x'*2049},{'cursor':'bad'}):
            with self.subTest(values=values), self.assertRaises(DomainError):
                list_issue_activity(self.actor,**dict({'issue_id':self.issue['id']},**values))

    def test_registry_invalid(self):
        from workpal.contracts import DomainError
        self.setup_issue()
        for values in ({'limit':True},{'cursor':42},{'limit':201},{'unexpected':'x'}):
            with self.subTest(values=values), self.assertRaises(DomainError): self.page(**values)

    def test_member_revoked(self):
        from workpal.contracts import DomainError
        self.setup_issue(); self.member.delete()
        with self.assertRaises(DomainError): self.page()

    def test_subject_unavailable(self):
        from workpal.access.models import RegisteredObject
        from workpal.contracts import DomainError
        self.setup_issue()
        RegisteredObject.objects.filter(kind='issue',object_id=str(self.issue['id'])).update(available=False)
        with self.assertRaises(DomainError): self.page()

    def test_pagination_and_cursor_scope(self):
        from workpal.contracts import DomainError
        from workpal.audit.models import AuditEvent
        from django.utils import timezone
        p=self.setup_issue()
        self.act(self.actor,'issue.update',{'issue_id':self.issue['id'],'title':'updated'},key='u',revision=1)
        AuditEvent.objects.filter(action_id__in=['issue.create','issue.update']).update(created_at=timezone.now())
        first=self.page(limit=1).data
        second=self.page(limit=1,cursor=first['next_cursor']).data
        self.assertNotEqual(first['items'][0]['id'],second['items'][0]['id'])
        self.assertEqual(second['next_cursor'],'')
        other=self.act(self.actor,'issue.create',{'project_id':p['id'],'title':'other'},key='other').data
        with self.assertRaises(DomainError): self.act(self.actor,'issue.activity.list',{'issue_id':other['id'],'cursor':first['next_cursor']})
        with self.assertRaises(DomainError): self.page(cursor=first['next_cursor']+'tampered')

    def test_fault_propagates_without_audit(self):
        from unittest.mock import patch
        from workpal.contracts import DomainError
        from workpal.audit.models import AuditEvent
        self.setup_issue(); before=AuditEvent.objects.count()
        with patch('workpal.audit.activity.authorize',side_effect=DomainError('unavailable','Unavailable',status=503)):
            with self.assertRaises(DomainError) as caught: self.page()
        self.assertEqual(caught.exception.status,503)
        self.assertEqual(AuditEvent.objects.count(),before)

    def test_hidden_history_before_paging_and_refs(self):
        from workpal.access.models import SourceGrant
        from workpal.audit.models import AuditEvent
        self.setup_issue()
        self.grant(self.a,read=True,write=True)
        comment=self.act(self.actor,'comment.create',{'issue_id':self.issue['id'],'body':'secret','source_refs':[{'kind':'source','id':'a'}]},key='c').data
        self.act(self.actor,'issue.update',{'issue_id':self.issue['id'],'title':'new'},key='u',revision=1)
        result=self.page()
        from workpal.contracts import ObjectRef
        self.assertIn(ObjectRef('source','a'),result.object_refs)
        audit=AuditEvent.objects.filter(action_id='issue.activity.list').latest('created_at')
        self.assertIn({'kind':'source','id':'a'},audit.scope_refs)
        SourceGrant.objects.filter(user=self.user).delete()
        first=self.page(limit=1).data
        second=self.page(limit=1,cursor=first['next_cursor']).data
        self.assertEqual([first['items'][0]['action_id'],second['items'][0]['action_id']],['issue.create','issue.update'])
        self.assertEqual(second['next_cursor'],'')

    def test_comment_confirmation_and_archived_history(self):
        self.setup_issue()
        comment=self.act(self.actor,'comment.create',{'issue_id':self.issue['id'],'body':'body'},key='c').data
        self.act(self.actor,'comment.update',{'comment_id':comment['id'],'body':'edit'},key='edit',revision=1)
        request={'comment_id':comment['id']}
        waiting=self.act(self.actor,'comment.remove',request,key='remove',revision=2)
        self.assertEqual(waiting.state,'waiting_confirmation')
        self.assertNotIn('comment.remove',[x['action_id'] for x in self.page().data['items']])
        self.act(self.actor,'comment.remove',request,key='remove',revision=2,confirmation_id=waiting.data['confirmation_id'])
        self.assertIn('comment.remove',[x['action_id'] for x in self.page().data['items']])
        self.act(self.actor,'comment.restore',request,key='restore',revision=3)
        archive=self.act(self.actor,'issue.archive',{'issue_id':self.issue['id']},key='archive',revision=1)
        if archive.state=='waiting_confirmation':
            self.act(self.actor,'issue.archive',{'issue_id':self.issue['id']},key='archive',revision=1,confirmation_id=archive.data['confirmation_id'])
        self.assertEqual([x['action_id'] for x in self.page().data['items']],['issue.create','comment.create','comment.update','comment.remove','comment.restore','issue.archive'])
