"""Session-bound, read-only canonical project access queries.

Caller owns the transaction and cancellation policy. Missing canonical tables
or query failures propagate; no legacy-record or empty-result fallback exists.
"""
from sqlalchemy import text,bindparam
from ..infrastructure.go_uuid import parse_uuid
from ..infrastructure.query_errors import NoRows


def _uuid(value):return None if value is None else parse_uuid(str(value))

class ProjectQueries:
    def __init__(self,session):self.session=session
    def _rows(self,sql,**params):return self.session.execute(text(sql),params)
    def _project(self,sql,identity):
        row=self._rows(sql,id=identity).first()
        if row is None:raise NoRows()
        return _uuid(row[0])
    def list_private_project_ids(self,workspace):
        return [_uuid(row[0]) for row in self._rows(
            "SELECT id FROM project WHERE workspace_id=:w AND visibility='private'",w=workspace)]
    def list_hidden_project_ids(self,workspace,user):
        return [_uuid(row[0]) for row in self._rows("""SELECT p.id FROM project p
            WHERE p.workspace_id=:w AND p.visibility='private' AND NOT EXISTS
            (SELECT 1 FROM project_member pm WHERE pm.project_id=p.id AND pm.user_id=:u)""",w=workspace,u=user)]
    def list_private_project_audience(self,workspace):
        return [(_uuid(row[0]),_uuid(row[1])) for row in self._rows("""SELECT p.id,pm.user_id
            FROM project p LEFT JOIN project_member pm ON pm.project_id=p.id
            WHERE p.workspace_id=:w AND p.visibility='private'""",w=workspace)]
    def get_member(self,workspace,user):
        row=self._rows('SELECT * FROM members WHERE workspace_id=:w AND user_id=:u',w=workspace,u=user).mappings().first()
        if row is None:raise NoRows()
        return dict(row)
    def issue_project(self,identity):return self._project('SELECT project_id FROM issue WHERE id=:id',identity)
    def comment_project(self,identity):return self._project('SELECT i.project_id FROM comment c JOIN issue i ON i.id=c.issue_id WHERE c.id=:id',identity)
    def autopilot_project(self,identity):return self._project('SELECT project_id FROM autopilot WHERE id=:id',identity)
    def get_task(self,identity):
        row=self._rows('SELECT * FROM agent_task_queue WHERE id=:id',id=identity).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        for key in ('id','agent_id','issue_id','chat_session_id','autopilot_run_id','originator_user_id','accountable_user_id'):
            result[key]=_uuid(result.get(key))
        return result
    def _batch(self,sql,identities):
        statement=text(sql).bindparams(bindparam('ids',expanding=True))
        return [(_uuid(row[0]),_uuid(row[1])) for row in self.session.execute(statement,{'ids':identities})]
    def list_issue_project_ids(self,identities):
        return self._batch('SELECT id,project_id FROM issue WHERE id IN :ids',identities)
    def list_autopilot_run_project_ids(self,identities):
        return self._batch('SELECT r.id,a.project_id FROM autopilot_run r JOIN autopilot a ON a.id=r.autopilot_id WHERE r.id IN :ids',identities)

    def get_issue(self,identity):
        row=self._rows('SELECT * FROM issue WHERE id=:id',id=identity).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        result['workspace_id']=_uuid(result.get('workspace_id'))
        return result
    def get_chat_session(self,identity):
        row=self._rows('SELECT * FROM chat_session WHERE id=:id',id=identity).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        for key in ('id','workspace_id','creator_id'):result[key]=_uuid(result.get(key))
        return result

    def get_agent(self,identity):
        row=self._rows('SELECT * FROM agent WHERE id=:id',id=identity).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        for key in ('id','workspace_id','owner_id'):result[key]=_uuid(result.get(key))
        return result

    def list_attachments_by_ids(self,workspace,identities):
        statement=text('SELECT * FROM attachment WHERE id IN :ids AND workspace_id=:w ORDER BY created_at ASC').bindparams(bindparam('ids',expanding=True))
        rows=self.session.execute(statement,{'ids':identities,'w':workspace}).mappings()
        result=[]
        for row in rows:
            item=dict(row)
            for key in ('id','workspace_id','issue_id','comment_id'):item[key]=_uuid(item.get(key))
            result.append(item)
        return result

    def _attachment(self,sql,**params):
        row=self._rows(sql,**params).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        for key in ('id','workspace_id','issue_id','comment_id'):
            result[key]=_uuid(result.get(key))
        return result

    def get_attachment(self,identity,workspace):
        return self._attachment('SELECT * FROM attachment WHERE id=:id AND workspace_id=:w',id=identity,w=workspace)

    def get_attachment_by_id(self,identity):
        return self._attachment('SELECT * FROM attachment WHERE id=:id',id=identity)

    def _chat_session(self,sql,identity,workspace):
        row=self._rows(sql,id=identity,w=workspace).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        for key in ('id','workspace_id','agent_id','creator_id','runtime_id','project_id'):
            result[key]=_uuid(result.get(key))
        return result

    def get_chat_session_in_workspace(self,identity,workspace):
        return self._chat_session('SELECT * FROM chat_session WHERE id=:id AND workspace_id=:w',identity,workspace)

    def get_public_chat_session_in_workspace(self,identity,workspace):
        return self._chat_session('''SELECT cs.* FROM chat_session cs
            WHERE cs.id=:id AND cs.workspace_id=:w AND
            (cs.explicitly_created_at IS NOT NULL OR EXISTS
             (SELECT 1 FROM chat_message m WHERE m.chat_session_id=cs.id
              AND m.message_kind != 'channel_command'))''',identity,workspace)

    def list_agent_invocation_targets(self,identity):
        rows=self._rows('''SELECT * FROM agent_invocation_target WHERE agent_id=:id
            ORDER BY target_type ASC,created_at ASC''',id=identity).mappings()
        result=[]
        for row in rows:
            target=dict(row)
            for key in ('id','agent_id','target_id','created_by'):
                target[key]=_uuid(target.get(key))
            result.append(target)
        return result

    def get_task_in_workspace(self,identity,workspace):
        row=self._rows('''SELECT t.* FROM agent_task_queue t JOIN agent a ON a.id=t.agent_id
            WHERE t.id=:id AND a.workspace_id=:w''',id=identity,w=workspace).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        for key in ('id','agent_id','issue_id','chat_session_id','autopilot_run_id','originator_user_id','accountable_user_id'):
            result[key]=_uuid(result.get(key))
        return result

    def get_issue_in_workspace(self,identity,workspace):
        row=self._rows('SELECT * FROM issue WHERE id=:id AND workspace_id=:w',id=identity,w=workspace).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        for key in ('id','workspace_id','project_id'):
            result[key]=_uuid(result.get(key))
        return result

    def get_comment(self,identity):
        row=self._rows('SELECT * FROM comment WHERE id=:id',id=identity).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        for key in ('id','workspace_id','issue_id'):
            result[key]=_uuid(result.get(key))
        return result

    def get_comment_in_workspace(self,identity,workspace):
        row=self._rows('SELECT * FROM comment WHERE id=:id AND workspace_id=:w',id=identity,w=workspace).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        for key in ('id','workspace_id','issue_id','author_id','parent_id','resolved_by_id','source_task_id','quick_action_id'):
            result[key]=_uuid(result.get(key))
        return result

    def list_reactions_by_comment_ids(self,identities):
        statement=text('''SELECT * FROM comment_reaction WHERE comment_id IN :ids
            ORDER BY created_at ASC''').bindparams(bindparam('ids',expanding=True))
        result=[]
        for row in self.session.execute(statement,{'ids':identities}).mappings():
            reaction=dict(row)
            for key in ('id','comment_id','workspace_id','actor_id'):
                reaction[key]=_uuid(reaction.get(key))
            result.append(reaction)
        return result

    def _attachments_for_parents(self,field,identities,workspace):
        statement=text(f'''SELECT * FROM attachment WHERE {field} IN :ids
            AND workspace_id=:w ORDER BY created_at ASC''').bindparams(bindparam('ids',expanding=True))
        result=[]
        for row in self.session.execute(statement,{'ids':identities,'w':workspace}).mappings():
            attachment=dict(row)
            for key in ('id','workspace_id','issue_id','comment_id','uploader_id','chat_session_id','chat_message_id','task_id','source_context_id'):
                attachment[key]=_uuid(attachment.get(key))
            result.append(attachment)
        return result

    def list_attachments_by_comment_ids(self,identities,workspace):
        return self._attachments_for_parents('comment_id',identities,workspace)

    def list_attachments_by_chat_message_ids(self,identities,workspace):
        return self._attachments_for_parents('chat_message_id',identities,workspace)

    def list_attachments_by_issue(self,identity,workspace):
        return self._attachments_for_parents('issue_id',[identity],workspace)

    def list_comment_origins_for_issue(self,identities,issue,workspace):
        statement=text('''SELECT id,author_type,author_id,created_at FROM comment
            WHERE id IN :ids AND issue_id=:issue AND workspace_id=:w
            AND deleted_at IS NULL''').bindparams(bindparam('ids',expanding=True))
        result=[]
        for row in self.session.execute(statement,{'ids':identities,'issue':issue,'w':workspace}).mappings():
            origin=dict(row)
            for key in ('id','author_id'):
                origin[key]=_uuid(origin.get(key))
            result.append(origin)
        return result

    def get_workspace(self,identity):
        row=self._rows('SELECT * FROM workspace WHERE id=:id',id=identity).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        result['id']=_uuid(result.get('id'))
        return result

    def get_issue_by_number(self,workspace,number):
        row=self._rows('SELECT * FROM issue WHERE workspace_id=:w AND number=:number',w=workspace,number=number).mappings().first()
        if row is None:raise NoRows()
        result=dict(row)
        for key in ('id','workspace_id','project_id'):
            result[key]=_uuid(result.get(key))
        return result
