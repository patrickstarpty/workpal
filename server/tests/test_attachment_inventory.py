import pytest
from workpal_backend.files.loader import AttachmentLoadError
A='attachment';C='comment';I='issue';W='workspace'
class Queries:
    def __init__(self,rows,origins=(),failure=''):self.rows=rows;self.origins=origins;self.failure=failure;self.calls=[]
    def list_attachments_by_issue(self,issue,workspace):
        self.calls.append(('attachments',issue,workspace))
        if self.failure=='attachments':raise RuntimeError('unavailable')
        return self.rows
    def list_comment_origins_for_issue(self,ids,issue,workspace):
        self.calls.append(('origins',ids,issue,workspace))
        if self.failure=='origins':raise RuntimeError('unavailable')
        return self.origins
class Metadata:
    def response(self,row,*,stable=False):return dict(id=row['id'],stable=stable)

def listing(q,stable=False):
    from workpal_backend.files.inventory import AttachmentInventory
    return AttachmentInventory(q,Metadata()).list(dict(id=I,workspace_id=W),stable=stable)


def test_comment_origin_query_deduplicates_preserves_first_seen_order_and_is_scoped():
    q=Queries([dict(id='1',comment_id=C),dict(id='2',comment_id='second'),dict(id='3',comment_id=C),dict(id='4',comment_id=None)],
        [dict(id=C,author_type='member',author_id=None,created_at=None)])
    result=listing(q,stable=True)
    assert q.calls==[('attachments',I,W),('origins',[C,'second'],I,W)]
    assert result[0]==dict(id='1',stable=True,comment_author_type='member',comment_author_id='',comment_created_at='')
    assert result[2]['comment_author_type']=='member'
    assert 'comment_author_type' not in result[1] and 'comment_author_type' not in result[3]

@pytest.mark.parametrize('rows',[[],[dict(id=A,comment_id=None)]])
def test_no_comment_parent_skips_origins_query(rows):
    q=Queries(rows)
    assert len(listing(q))==len(rows)
    assert q.calls==[('attachments',I,W)]

@pytest.mark.parametrize('failure',['attachments','origins'])
def test_list_and_origin_failures_have_same_response(failure):
    with pytest.raises(AttachmentLoadError) as caught:listing(Queries([dict(id=A,comment_id=C)],failure=failure))
    assert caught.value.status==500 and caught.value.message=='failed to list attachments'


def test_http_listing_loads_issue_before_attachment_query_and_preserves_errors():
    import asyncio,json
    from workpal_backend.issues.loader import IssueLoadError
    from workpal_backend.files.inventory import AttachmentListing
    q=Queries([])
    class Loader:
        def for_user(self,identity,user,workspace):
            q.calls.append(('issue',identity,user,workspace))
            if identity=='hidden':raise IssueLoadError(404,'issue not found')
            return dict(id=I,workspace_id=W)
    from workpal_backend.files.inventory import AttachmentInventory
    service=AttachmentListing(Loader(),AttachmentInventory(q,Metadata()))
    response=asyncio.run(service.list('visible','user',W))
    assert response.status_code==200 and json.loads(response.body)==[]
    assert q.calls==[('issue','visible','user',W),('attachments',I,W)]
    q.calls=[]
    response=asyncio.run(service.list('hidden','user',W))
    assert response.status_code==404 and json.loads(response.body)=={'error':'issue not found'}
    assert q.calls==[('issue','hidden','user',W)]


def test_comment_origins_keep_original_struct_field_order():
    from workpal_backend.files.inventory import AttachmentInventory
    class FullMetadata:
        def response(self,row,*,stable=False):return dict(id=row['id'],markdown_url='url',content_type='text/plain',size_bytes=3)
    q=Queries([dict(id=A,comment_id=C)],[dict(id=C,author_type='member',author_id=None,created_at=None)])
    response=AttachmentInventory(q,FullMetadata()).list(dict(id=I,workspace_id=W))[0]
    assert list(response)==['id','markdown_url','comment_author_type','comment_author_id','comment_created_at','content_type','size_bytes']
