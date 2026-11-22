"""Request-scoped attachment writes using caller-owned database and storage.

Identity fields must come from authentication, after stripping untrusted actor
headers. Transaction/query providers must implement the canonical lock SQL.
"""
from functools import partial

from ..auth.wakeup_actor import capture_wakeup_actor
from ..comments.groups import CommentGroups
from ..comments.projection import comment_response
from ..infrastructure.uuid7 import uuid7
from .attachment_io import _joined_call
from .deletion import AttachmentDeletion
from .events import AttachmentEvents
from .loader import AttachmentLoader
from .upload_bindings import UploadBindings
from .uploads import AttachmentUploads
from .write_transactions import AttachmentWriter


class AttachmentMutations:
    def __init__(self, queries, begin, queries_for, storage, metadata, publish, *,
                 user_id, workspace_id, hidden_projects, actor_source='', agent_id='',
                 task_id='', member=None, stable=False, request_error=lambda: None,
                 cached_actor=None, handed_to='', new_id=uuid7):
        self.queries, self.begin, self.queries_for = queries, begin, queries_for
        self.storage, self.metadata = storage, metadata
        self.user, self.workspace = user_id, workspace_id
        self.hidden_projects, self.request_error = hidden_projects, request_error
        self.actor = dict(actor_source=actor_source, agent_id=agent_id, task_id=task_id)
        self.member, self.stable = member, stable
        self.cached_actor, self.handed_to, self.new_id = cached_actor, handed_to, new_id
        groups = CommentGroups(queries, metadata, workspace_id=workspace_id, stable=stable)
        self.events = AttachmentEvents(queries, publish, groups.reactions, groups.attachments,
            comment_response, workspace_id=workspace_id, uploader_type='member', uploader_id=user_id)

    async def _writer(self):
        actor = await _joined_call(partial(capture_wakeup_actor, cached=self.cached_actor,
            **self.actor), self.queries, self.user, self.workspace)
        return AttachmentWriter(self.begin, self.queries_for, actor=actor, handed_to=self.handed_to)

    async def upload(self, body, content_type, *, raw_query=b''):
        writer = await self._writer()
        bindings = UploadBindings(self.queries, hidden_projects=self.hidden_projects,
                                  request_error=self.request_error)
        service = AttachmentUploads(self.storage, bindings, writer, self.metadata,
                                    on_created=self.events, new_id=self.new_id)
        return await service.upload(body, content_type, self.user, self.workspace,
            raw_query=raw_query, stable=self.stable, request_error=self.request_error, **self.actor)

    async def delete(self, attachment_id):
        writer = await self._writer()
        loader = AttachmentLoader(self.queries, hidden_projects=self.hidden_projects,
                                  request_error=self.request_error)
        return await AttachmentDeletion(loader, writer, self.events, self.storage).delete(
            attachment_id, self.user, self.workspace, member=self.member)
