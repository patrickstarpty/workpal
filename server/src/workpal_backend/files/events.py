"""Attachment events after the corresponding transaction commits."""
from asyncio import CancelledError


class AttachmentEvents:
    def __init__(self, queries, publish, group_reactions, group_attachments,
                 comment_response, *, workspace_id, uploader_type, uploader_id):
        self.queries = queries
        self.publish = publish
        self.group_reactions = group_reactions
        self.group_attachments = group_attachments
        self.comment_response = comment_response
        self.actor = (workspace_id, uploader_type, uploader_id)

    def __call__(self, attachment, uploader=None):
        actor = self.actor if uploader is None else (self.actor[0], *uploader)
        issue = attachment.get('issue_id')
        if attachment.get('issue_revision', 0) > 0 and issue is not None:
            self.publish('issue_attachments:changed', *actor, {
                'issue_id':issue, 'issue_revision':attachment['issue_revision'],
            })
        comment_id = attachment.get('comment_id')
        if attachment.get('comment_revision', 0) <= 0 or comment_id is None:
            return
        self._comment(attachment, actor=actor)

    def deleted(self, attachment, deleted):
        if not deleted['changed']:
            return
        issue = attachment.get('issue_id')
        if issue is not None:
            self.publish('issue_attachments:changed', *self.actor, {
                'issue_id':issue, 'issue_revision':deleted['issue_revision'],
            })
        if attachment.get('comment_id') is not None:
            self._comment(attachment)

    def _comment(self, attachment, *, actor=None):
        comment_id = attachment['comment_id']
        try:
            comment = self.queries.get_comment_in_workspace(comment_id, attachment['workspace_id'])
        except (Exception, CancelledError):
            return
        identity = comment['id']
        reactions = self.group_reactions([identity])
        attachments = self.group_attachments([identity])
        response = self.comment_response(comment, (reactions or {}).get(identity),
                                         (attachments or {}).get(identity))
        self.publish('comment:updated', *(self.actor if actor is None else actor), {'comment':response})
