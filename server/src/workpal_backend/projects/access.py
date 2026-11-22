"""Private projects require membership from every human bounding a viewer.

Inputs are canonical nullable UUIDs, not raw request values. Query adapters must
apply the actual workspace/project membership SQL; errors propagate unchanged.
"""
from ..infrastructure.go_uuid import parse_uuid
from ..infrastructure.query_errors import NoRows


def valid_visibility(value):return value in ('workspace','private')
def is_manager_role(role):return role in ('owner','admin')

class Hidden:
    def __init__(self):self._ids=[];self._set=set()
    def add(self,identities):
        for identity in identities or ():
            if identity is None:continue
            identity=parse_uuid(identity)
            if identity not in self._set:
                self._set.add(identity);self._ids.append(identity)
    def empty(self):return not self._ids
    def can_see_project(self,identity):
        return identity is None or not self._set or parse_uuid(identity) not in self._set
    def can_see_projects(self,identities):return all(self.can_see_project(identity) for identity in identities or ())
    def param(self):return self._ids or None
    def ids(self):return self._ids


def for_member(queries,workspace,user):
    hidden=Hidden()
    hidden.add(queries.list_hidden_project_ids(workspace,user))
    return hidden


def for_principals(queries,workspace,*principals):
    hidden=Hidden()
    private=queries.list_private_project_ids(workspace)
    if not private:return hidden
    all_private=Hidden();all_private.add(private)
    seen=set();valid=[]
    for principal in principals:
        if principal is None:continue
        principal=parse_uuid(principal)
        if principal not in seen:
            seen.add(principal);valid.append(principal)
    if not valid:return all_private
    for principal in valid:
        try:queries.get_member(workspace,principal)
        except NoRows:return all_private
        hidden.add(for_member(queries,workspace,principal).ids())
    return hidden


def run_principals(task,agent_owner):
    originator=task.get('originator_user_id')
    if originator is None:originator=task.get('accountable_user_id')
    return [originator,agent_owner]
