"""Private-project audience cache over an injected canonical query interface.

Query adapters and cancellation deadlines remain the caller's responsibility;
this module never substitutes legacy records for missing canonical relations.
"""
from threading import RLock
from time import monotonic
from ..infrastructure.go_uuid import parse_uuid
from .event_refs import extract_event_refs
from .task_projects import task_projects

from ..infrastructure.query_errors import NoRows

VISIBLE_TASK_EVENTS=frozenset('task:'+suffix for suffix in (
    'queued','coalesced','dispatch','running','waiting_local_directory','usage',
    'completed','failed','cancelled'))
INVALIDATE_TASK_EVENTS=frozenset('task:'+suffix for suffix in ('queued','completed','failed','cancelled'))

class PrivateProjectAudience:
    def __init__(self,queries,*,now=monotonic,ttl=2):
        self.q=queries;self.now=now;self.ttl=ttl
        self._lock=RLock();self._workspaces={};self._tasks={}

    def __call__(self,event):
        workspace=event.get('workspaceID','');kind=event.get('type','')
        if not workspace:return None,False
        invalidates=kind.startswith(('project:','member:'))
        with self._lock:
            if invalidates or kind.startswith(('issue:','autopilot:')):
                for key in list(self._tasks):
                    if key[0]==workspace:del self._tasks[key]
            elif kind in INVALIDATE_TASK_EVENTS:
                self._tasks.pop((workspace,event.get('taskID','')),None)
        if kind in VISIBLE_TASK_EVENTS:return None,False
        if invalidates:
            with self._lock:self._workspaces.pop(workspace,None)
        projects=self._workspace(workspace)
        if not projects:return None,False
        members=None;private=False
        for project in self._event_projects(event):
            if project not in projects:continue
            group=projects[project]
            if not private:members=group;private=True
            else:
                allowed=set(group or ())
                # Go a[:0:0] preserves nil only if the first slice is nil.
                members=None if members is None else [user for user in members if user in allowed]
        return members,private

    def _workspace(self,workspace):
        with self._lock:cached=self._workspaces.get(workspace)
        if cached is not None and self.now()-cached[0]<self.ttl:return cached[1]
        try:identity=parse_uuid(workspace)
        except ValueError:return {}
        rows=self.q.list_private_project_audience(identity)
        loaded_at=self.now();projects={}
        for project,user in rows:
            project=parse_uuid(project) if project is not None else ''
            projects.setdefault(project,None)
            if user is not None:
                if projects[project] is None:projects[project]=[]
                projects[project].append(parse_uuid(user))
        with self._lock:self._workspaces[workspace]=(loaded_at,projects)
        return projects

    def _lookup(self,identity,query):
        try:identity=parse_uuid(identity)
        except ValueError:return []
        try:project=query(identity)
        except NoRows:return []
        return [parse_uuid(project) if project is not None else '']

    def _event_projects(self,event):
        refs=extract_event_refs(event.get('type',''),event.get('payload'))
        if refs.project_known:return [refs.project_id]
        if refs.issue_id:return self._lookup(refs.issue_id,self.q.issue_project)
        if refs.comment_id:return self._lookup(refs.comment_id,self.q.comment_project)
        if refs.linked_issue_ids:
            return [project for issue in refs.linked_issue_ids for project in self._lookup(issue,self.q.issue_project)]
        if refs.autopilot_id:return self._lookup(refs.autopilot_id,self.q.autopilot_project)
        if event.get('taskID') and not event.get('chatSessionID'):return self._task_projects(event)
        return []

    def _task_projects(self,event):
        key=(event['workspaceID'],event['taskID'])
        with self._lock:cached=self._tasks.get(key)
        if cached is not None and self.now()-cached[0]<self.ttl:return cached[1]
        try:identity=parse_uuid(event['taskID'])
        except ValueError:return []
        try:task=self.q.get_task(identity)
        except NoRows:return []
        projects=[parse_uuid(project) for project in (task_projects(self.q,task) or ())]
        with self._lock:
            if len(self._tasks)>=4096:self._tasks.clear()
            self._tasks[key]=(self.now(),projects)
        return projects
