from datetime import datetime,timezone,timedelta
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
B='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
BASE=dict(id=A,issue_id=B,author_type='member',author_id=None,content='hello',type='text',created_at=None,updated_at=datetime(2026,11,22,12,30,45,999999,tzinfo=timezone(timedelta(hours=8))),revision=4)


def test_comment_projection_null_fields_empty_collections_and_omissions():
    from workpal_backend.comments.projection import comment_response
    response=comment_response(BASE,None,None)
    assert response==dict(id=A,issue_id=B,author_type='member',author_id='',content='hello',type='text',parent_id=None,created_at='',updated_at='2026-11-22T12:30:45+08:00',revision=4,resolved_at=None,resolved_by_type=None,resolved_by_id=None,reactions=[],attachments=[])


def test_comment_projection_keeps_tombstone_data_as_supplied_without_inventing_cleanup():
    from workpal_backend.comments.projection import comment_response
    row=dict(BASE,source_task_id=B,quick_action_id=A,parent_id=B,deleted_at=BASE['updated_at'],resolved_at=BASE['updated_at'],resolved_by_type='',resolved_by_id=A)
    reactions=[{'id':'reaction'}];attachments=[{'id':'attachment'}]
    response=comment_response(row,reactions,attachments)
    assert response['deleted_at']=='2026-11-22T12:30:45+08:00'
    assert response['content']=='hello' and response['reactions']==reactions and response['attachments']==attachments
    assert response['resolved_by_type']=='' and response['source_task_id']==B
    assert 'issue_revision' not in response


def test_reaction_projection_omits_nonpositive_revision_and_formats_invalid_time():
    from workpal_backend.comments.projection import reaction_response
    row=dict(id=A,comment_id=B,actor_type='member',actor_id=None,emoji='👍',created_at=None,comment_revision=0)
    response=reaction_response(row)
    assert response==dict(id=A,comment_id=B,actor_type='member',actor_id='',emoji='👍',created_at='')
    assert 'comment_revision' not in reaction_response(dict(row,comment_revision=5))
    assert reaction_response(dict(row,comment_revision=5),added=True)['comment_revision']==5
