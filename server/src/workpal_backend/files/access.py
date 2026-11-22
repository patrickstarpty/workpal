"""Attachment parent visibility against a request's resolved hidden projects."""
from ..infrastructure.query_errors import NoRows


def attachment_in_hidden_project(queries, hidden, attachment):
    if hidden.empty():
        return False
    try:
        if attachment.get('issue_id') is not None:
            project = queries.issue_project(attachment['issue_id'])
        elif attachment.get('comment_id') is not None:
            project = queries.comment_project(attachment['comment_id'])
        else:
            return False
    except NoRows:
        return False
    return not hidden.can_see_project(project)


def visible_attachment_ids(queries, hidden, workspace, identities):
    if not identities or hidden.empty():
        return identities
    attachments = queries.list_attachments_by_ids(workspace, identities)
    drop = {attachment['id']: attachment_in_hidden_project(queries, hidden, attachment)
            for attachment in attachments}
    return [identity for identity in identities if not drop.get(identity, False)]
