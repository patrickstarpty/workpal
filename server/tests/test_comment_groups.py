import asyncio
import pytest
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
class Queries:
    def __init__(self):self.calls=[];self.failure=False
    def call(self,name,*args):
        self.calls.append((name,*args))
        if self.failure:raise asyncio.CancelledError()
    def list_reactions_by_comment_ids(self,ids):
        self.call('reactions',ids)
        return [dict(id=A,comment_id=A,actor_type='member',actor_id=None,emoji='👍',created_at=None)]
    def list_attachments_by_comment_ids(self,ids,workspace):
        self.call('comments',ids,workspace);return [dict(id='1',comment_id=A),dict(id='2',comment_id=A)]
    def list_attachments_by_chat_message_ids(self,ids,workspace):
        self.call('messages',ids,workspace);return [dict(id='1',chat_message_id=A)]
class Metadata:
    def response(self,row,*,stable=False):return dict(id=row['id'],stable=stable)

def groups(q,**kwargs):
    from workpal_backend.comments.groups import CommentGroups
    return CommentGroups(q,Metadata(),workspace_id=W,**kwargs)


def test_empty_groups_do_not_query_and_keep_nil():
    q=Queries();g=groups(q)
    assert g.reactions([]) is None and g.attachments([]) is None and g.chat_attachments([]) is None
    assert q.calls==[]


def test_reaction_projection_and_attachment_order_preserved():
    q=Queries();g=groups(q,stable=True)
    assert g.reactions([A])[A][0]['actor_id']==''
    assert g.attachments([A])=={A:[dict(id='1',stable=True),dict(id='2',stable=True)]}
    assert q.calls==[('reactions',[A]),('comments',[A],W)]


def test_chat_message_attachments_remain_signed_even_for_stable_list_client():
    q=Queries()
    assert groups(q,stable=True).chat_attachments([A])=={A:[dict(id='1',stable=False)]}

@pytest.mark.parametrize('method',['reactions','attachments','chat_attachments'])
def test_group_query_failure_returns_nil(method):
    q=Queries();q.failure=True
    assert getattr(groups(q),method)([A]) is None
