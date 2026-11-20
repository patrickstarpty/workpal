"""Closed JSON views shared by action adapters."""
def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)
I = dict(type='integer')
S = dict(type='string')
COMMENT = obj(dict(id=I, issue_id=I, author_user_id=I, body=S,
    archived=dict(type="boolean"), updated_at=S, mentions=dict(type='array',items=I), revision=I, created_at=S))
SUBSCRIPTION = obj(dict(issue_id=I, subscribed=dict(type='boolean')))
NOTIFICATION = obj(dict(id=I, issue_id=I, comment_id=I, kind=S,
    issue_title=S, revision=I, read_at=S, created_at=S))
def page(view):
    return obj(dict(items=dict(type='array',items=view),next_cursor=I))
