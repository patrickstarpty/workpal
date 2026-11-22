"""Batch reaction/attachment projection for already-authorized parent objects."""
from asyncio import CancelledError
from ..infrastructure.go_uuid import parse_uuid
from .projection import reaction_response


class CommentGroups:
    def __init__(self, queries, metadata, *, workspace_id, stable=False):
        self.queries, self.metadata = queries, metadata
        try:
            self.workspace = parse_uuid(workspace_id)
        except ValueError:
            self.workspace = None
        self.stable = stable

    def reactions(self, identities):
        if not identities:
            return None
        try:
            rows = self.queries.list_reactions_by_comment_ids(identities)
        except (Exception, CancelledError):
            return None
        grouped = {}
        for row in rows:
            grouped.setdefault(row.get('comment_id') or '', []).append(reaction_response(row))
        return grouped

    def _attachments(self, identities, *, chat):
        if not identities:
            return None
        query = self.queries.list_attachments_by_chat_message_ids if chat else self.queries.list_attachments_by_comment_ids
        try:
            rows = query(identities, self.workspace)
        except (Exception, CancelledError):
            return None
        grouped = {}
        for row in rows:
            parent = row.get('chat_message_id' if chat else 'comment_id') or ''
            grouped.setdefault(parent, []).append(self.metadata.response(row, stable=False if chat else self.stable))
        return grouped

    def attachments(self, identities):
        return self._attachments(identities, chat=False)

    def chat_attachments(self, identities):
        return self._attachments(identities, chat=True)
