"""Member and tenant checks through public interfaces."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from tests import test_graph_instances as fixtures
from tests import test_graph_instances_review as review
from workpal.contracts import Actor, SubjectRef, ObjectRef, DomainError
from workpal.identity.models import Workspace, Membership
from workpal.access import service as access
from workpal.access.models import SourceGrant
from workpal.agents import service as agents
from workpal.work import service, issues
from workpal.workflows import instances, persistence as p


class GraphInstancePermissions(TestCase):
    setUp = fixtures.GraphInstanceTests.setUp
    rows = review.GraphInstanceReview.rows
    denied = review.GraphInstanceReview.denied

    def graph(self, actor, agent_ids, inputs):
        ids=['s']+['t'+str(i) for i in range(len(agent_ids))]+['e']
        definition=dict(nodes=[dict(id='s',type='start',config={})]+[dict(id=ids[i+1],type='agent_task',config=dict(agent_id=a,input_refs=inputs)) for i,a in enumerate(agent_ids)]+[dict(id='e',type='end',config={})],edges=[dict(**{'from':a,'to':b},on='always',required=True,max_traversals=0) for a,b in zip(ids,ids[1:])],declared_fields=[])
        draft=p.create(actor,'Permissions',definition)
        return p.publish(actor,draft['id'],1)

    def init(self, actor, issue, version, key):
        return instances.initialize(actor,SubjectRef('issue',str(issue['id'])),version['id'],key)

    def test_member_unique_agents_and_independent_read_sources(self):
        owner=self.actor
        user=get_user_model().objects.create(username='ordinary-member')
        Membership.objects.create(user=user,workspace_id=owner.workspace_id,role='member')
        member=Actor(user.pk,owner.workspace_id)
        second=agents.create(owner,'Second')
        roots=[ObjectRef('document','agent-root'),ObjectRef('document','input-root')]
        grants=[]
        for root in roots:
            access.register_object(owner.workspace_id,root,is_source=True)
            for actor in (owner,member):
                grant=SourceGrant.objects.create(user_id=actor.user_id,source=access.resolve(root),read=True,write=True,publish=True)
                if actor==member: grants.append(grant)
        access.register_object(owner.workspace_id,agents.ref(self.agent['id']),[roots[0]])
        input_ref=ObjectRef('document','direct-input')
        access.register_object(owner.workspace_id,input_ref,[roots[1]])
        version=self.graph(owner,[second['id'],self.agent['id'],self.agent['id']],['document:direct-input'])
        before=self.rows()
        old=self.init(member,self.issue,version,'member')
        after=self.rows()
        for table in before:
            if table.startswith(('agents_','execution_','work_')):
                self.assertEqual(before[table],after[table])
        self.assertEqual(old['snapshot']['agents'],sorted([self.agent,second],key=lambda a:a['id']))
        expected=[issues.ref(self.issue['id']),service.ref(self.issue['project_id']),issues.requirement_ref(self.issue['requirements_version_id']),p.ref(version['id'],version=True),agents.ref(self.agent['id']),agents.ref(second['id']),input_ref]+roots
        self.assertEqual({(r['kind'],r['id']) for r in old['snapshot']['source_refs']},{(r.kind,r.id) for r in expected})
        for grant in grants:
            grant.write=False; grant.save()
            self.assertEqual(self.init(member,self.issue,version,'member'),old)
            self.init(member,self.issue,version,'readonly'+str(grant.pk))
            grant.read=False; grant.save()
            self.denied(lambda:self.init(member,self.issue,version,'member'),403)
            self.denied(lambda:self.init(member,self.issue,version,'denied'+str(grant.pk)),403)
            self.denied(lambda:instances.read(member,old['id']),403)
            grant.read=True; grant.save()
            self.assertEqual(self.init(member,self.issue,version,'member'),old)

    def test_two_memberships_cross_workspace_conflicts_and_strict_ids(self):
        owner=self.actor
        other=Workspace.objects.create(name='Other permissions')
        Membership.objects.create(user_id=owner.user_id,workspace=other,role='owner')
        other_owner=Actor(owner.user_id,other.pk)
        user=get_user_model().objects.create(username='both-member')
        for workspace in (owner.workspace_id,other.pk): Membership.objects.create(user=user,workspace_id=workspace,role='member')
        member=Actor(user.pk,owner.workspace_id); other_member=Actor(user.pk,other.pk)
        foreign_agent=agents.create(other_owner,'Foreign')
        project=service.create(other_owner,'Other project')
        foreign_issue=issues.create(other_owner,project['id'],'Other issue')
        foreign_input=ObjectRef('document','foreign-input')
        access.register_object(other.pk,foreign_input,is_source=True)
        for actor in (other_owner,other_member): SourceGrant.objects.create(user_id=actor.user_id,source=access.resolve(foreign_input),read=True,write=True,publish=True)
        foreign_version=self.graph(other_owner,[foreign_agent['id']],['document:foreign-input'])
        self.init(other_member,foreign_issue,foreign_version,'foreign-positive')
        old=self.init(member,self.issue,self.version,'local')
        self.denied(lambda:self.init(member,foreign_issue,self.version,'cross-subject'),404)
        self.denied(lambda:self.init(member,self.issue,foreign_version,'cross-version'),404)
        for agent_ids,inputs in (([foreign_agent['id']],[]),([self.agent['id']],['document:foreign-input']),([foreign_agent['id']],['document:foreign-input'])):
            self.denied(lambda:self.graph(owner,agent_ids,inputs),404 if foreign_agent['id'] in agent_ids else 403)
        another=issues.create(owner,self.issue['project_id'],'Another')
        version=self.graph(owner,[self.agent['id']],[])
        for issue,v in ((another,self.version),(self.issue,version)):
            self.init(member,issue,v,'positive'+str(issue['id'])+str(v['id']))
            self.denied(lambda:self.init(member,issue,v,'local'),409)
            self.assertEqual(self.init(member,self.issue,self.version,'local'),old)
        for bad in (True,'1',0,-1,2**63,'01'):
            self.denied(lambda:instances.initialize(member,SubjectRef('issue',str(self.issue['id'])),bad,'bad'),400)
            self.denied(lambda:instances.read(member,bad),400)
        for bad in (True,1,0,-1,'0','-1','01',str(2**63),' 1','+1'):
            self.denied(lambda:instances.initialize(member,SubjectRef('issue',bad),self.version['id'],'bad-subject'),400)
        for bad_subject in ({'type':'issue','id':str(self.issue['id'])},SubjectRef('project',str(self.issue['id'])),SubjectRef(True,str(self.issue['id']))):
            self.denied(lambda:instances.initialize(member,bad_subject,self.version['id'],'bad-type'),400)
        self.assertEqual(instances.read(member,old['id']),old)
