"""Read current human approval facts in one local transaction."""
from dataclasses import asdict
from workpal.storage import atomic_write
from workpal.access.service import authorize
from . import service, review
from .models import Delivery, DeliveryCurrent, Review


def inspect(actor, subject):
    def read():
        issue = service._subject_issue(actor, subject)
        req = issue.current_requirements
        refs = [service.issues.ref(issue.pk), service.issues.requirement_ref(req.pk)]
        authorize(actor, 'read', refs)
        data = dict(subject=asdict(subject), status='not_approved', reason='no_current_delivery',
            current_revision=1, current_delivery_id=0, current_delivery_number=0,
            review_id=0, review_revision=0, requirements_revision=req.number,
            completion_policy=issue.workflow_snapshot['definition']['review_policy']['completion'])
        current = DeliveryCurrent.objects.filter(workspace_id=actor.workspace_id,
            subject_type=subject.type, subject_id=subject.id).values('id','revision','current_delivery_id').first()
        if not current: return data, refs
        target_ref = service.ref(current['current_delivery_id'])
        authorize(actor, 'read', [target_ref])
        refs.append(target_ref)
        paths = ['requirements_snapshot__'+key for key in ('id','number','sha256')]
        target = Delivery.objects.filter(pk=current['current_delivery_id'], workspace_id=actor.workspace_id,
            subject_type=subject.type, subject_id=subject.id).values('id','number','sha256','workflow_snapshot__sha256',*paths).first()
        if target is None:
            review.conflict('submission_changed')
        data.update(current_revision=current['revision'], current_delivery_id=target['id'],
            current_delivery_number=target['number'], reason='review_required')
        decision = Review.objects.filter(current_id=current['id'],revision=current['revision'],
            workspace_id=actor.workspace_id).values('id','revision','delivery_id','version',
                'delivery_sha256','workflow_snapshot__sha256','outcome',*paths).first()
        if not decision: return data, refs
        decision_ref = review.ref(decision['id'])
        authorize(actor, 'read', [decision_ref])
        refs.append(decision_ref)
        data.update(review_id=decision['id'],review_revision=decision['revision'])
        if (decision['delivery_id'] != target['id'] or decision['version'] != target['number']
            or decision['delivery_sha256'] != target['sha256']
            or decision['workflow_snapshot__sha256'] != target['workflow_snapshot__sha256']):
            data['reason'] = 'submission_changed'
        elif decision['outcome'] == 'request_changes': data['reason'] = 'changes_requested'
        elif decision['outcome'] != 'approve': data['reason'] = 'submission_changed'
        elif any(row['requirements_snapshot__'+key] != value
                 for row in (target,decision) for key,value in
                 (('id',req.pk),('number',req.number),('sha256',req.sha256))):
            data['reason'] = 'requirements_changed'
        else: data.update(status='approved',reason='approved')
        return data, list(dict.fromkeys(refs))
    return atomic_write(read)
