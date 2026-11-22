import pytest
I='issue';C='comment';W='workspace'
class Queries:
    def __init__(self,log,failure=False):self.log=log;self.failure=failure
    def get_comment_in_workspace(self,identity,workspace):
        self.log.append(('comment',identity,workspace))
        if self.failure:raise RuntimeError('unavailable')
        return dict(id=C,content='body')

def service(log,failure=False):
    from workpal_backend.files.events import AttachmentEvents
    def publish(*args):log.append(('publish',*args))
    def reactions(ids):log.append(('reactions',ids));return {C:['reaction']}
    def attachments(ids):log.append(('attachments',ids));return {C:['attachment']}
    def comment_response(row,reactions,attachments):return dict(content=row['content'],reactions=reactions,attachments=attachments)
    return AttachmentEvents(Queries(log,failure),publish,reactions,attachments,comment_response,workspace_id=W,uploader_type='member',uploader_id='user')


def test_upload_revision_events_follow_original_order_and_reloaded_comment():
    log=[]
    service(log)(dict(issue_id=I,issue_revision=2,comment_id=C,comment_revision=3,workspace_id=W))
    assert log==[
        ('publish','issue_attachments:changed',W,'member','user',{'issue_id':I,'issue_revision':2}),
        ('comment',C,W),('reactions',[C]),('attachments',[C]),
        ('publish','comment:updated',W,'member','user',{'comment':{'content':'body','reactions':['reaction'],'attachments':['attachment']}}),
    ]


def test_zero_revisions_do_not_publish_or_reload():
    log=[];service(log)(dict(issue_id=I,issue_revision=0,comment_id=C,comment_revision=0,workspace_id=W))
    assert log==[]


def test_missing_parent_ids_do_not_publish_positive_revision():
    log=[];service(log)(dict(issue_id=None,issue_revision=3,comment_id=None,comment_revision=4,workspace_id=W))
    assert log==[]


def test_comment_reload_failure_skips_comment_event_without_losing_issue_event():
    log=[];service(log,True)(dict(issue_id=I,issue_revision=2,comment_id=C,comment_revision=3,workspace_id=W))
    assert [item[0] for item in log]==['publish','comment']


def test_delete_changed_emits_even_zero_revision_and_reloads_original_parent():
    log=[]
    service(log).deleted(dict(issue_id=I,comment_id=C,workspace_id=W),dict(changed=True,issue_revision=0))
    assert log[0]==('publish','issue_attachments:changed',W,'member','user',{'issue_id':I,'issue_revision':0})
    assert log[1:4]==[('comment',C,W),('reactions',[C]),('attachments',[C])]
    assert log[-1][1]=='comment:updated'


def test_unchanged_delete_does_not_emit_or_reload():
    log=[]
    service(log).deleted(dict(issue_id=I,comment_id=C,workspace_id=W),dict(changed=False,issue_revision=7))
    assert log==[]


def test_upload_event_override_preserves_resolved_raw_actor_on_issue_and_comment_events():
    log=[]
    service(log)(dict(issue_id=I,issue_revision=2,comment_id=C,comment_revision=3,workspace_id=W),('agent','RAW-ACTOR'))
    assert [entry[3:5] for entry in log if entry[0]=='publish']==[('agent','RAW-ACTOR'),('agent','RAW-ACTOR')]
