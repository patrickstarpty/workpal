from tests.support import WorkpalCase
from tests.test_review_validation import ReviewFixtures

class ApprovalTests(ReviewFixtures, WorkpalCase):
    def test_registry_no_current(self):
        result = self.act(self.actor, 'delivery.approval.read', dict(subject=self.subject))
        self.assertEqual(result.data['reason'], 'no_current_delivery')

    def read_approval(self):
        return self.act(self.actor, 'delivery.approval.read', dict(subject=self.subject)).data

    def test_selected_requires_review(self):
        self.ready()
        self.assertEqual(self.read_approval()['reason'], 'review_required')

    def test_approved(self):
        self.decide(self.ready())
        self.assertEqual(self.read_approval()['status'], 'approved')

    def test_returned(self):
        self.decide(self.ready(), outcome='request_changes')
        self.assertEqual(self.read_approval()['reason'], 'changes_requested')

    def test_reselection_invalidates(self):
        target=self.ready()
        self.decide(target)
        self.choose(target, 'again', 3)
        self.assertEqual(self.read_approval()['reason'], 'review_required')

    def test_new_decision(self):
        target=self.ready()
        self.decide(target)
        self.decide(target,key='returned',revision=3,outcome='request_changes')
        self.assertEqual(self.read_approval()['reason'], 'changes_requested')

    def test_changed_requirements(self):
        self.decide(self.ready())
        self.act(self.actor,'issue.update',dict(issue_id=self.issue['id'],title='Changed'),key='change',revision=1)
        self.assertEqual(self.read_approval()['reason'],'requirements_changed')

    def test_direct_interface(self):
        from workpal.delivery import approval
        from workpal.contracts import SubjectRef
        data,refs=approval.inspect(self.actor,SubjectRef(**self.subject))
        self.assertEqual(data['current_revision'],1)
        self.assertEqual(len(refs),2)

    def test_closed_input(self):
        from workpal.contracts import DomainError
        with self.assertRaises(DomainError):
            self.act(self.actor,'delivery.approval.read',dict(subject=self.subject,extra=True))

    def test_executor_read(self):
        from workpal.contracts import Actor
        from workpal.access.models import SourceGrant
        self.decide(self.ready())
        SourceGrant.objects.filter(user=self.user).update(write=False)
        self.actor=Actor(self.user.pk,self.workspace.pk,executor_id='reader')
        self.assertEqual(self.read_approval()['status'],'approved')
