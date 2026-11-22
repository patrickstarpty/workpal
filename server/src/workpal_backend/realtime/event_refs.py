"""Project audience references from the JSON representation of event payloads."""
from dataclasses import dataclass
import json
from ..infrastructure.go_response import GoJSONEncoder

# The frozen !oss build registers this EE project event at initialization.
DEFAULT_PROJECT_EVENTS=frozenset({'project_folder:filed'})

@dataclass
class EventRefs:
    project_known: bool=False
    project_id: str=''
    issue_id: str=''
    comment_id: str=''
    autopilot_id: str=''
    linked_issue_ids: list[str] | None=None


def extract_event_refs(event_type,payload,*,project_events=DEFAULT_PROJECT_EVENTS):
    refs=EventRefs()
    try:
        top=json.loads(json.dumps(payload,cls=GoJSONEncoder,allow_nan=False))
    except (ValueError,TypeError,RecursionError,UnicodeError):
        return refs
    if not isinstance(top,dict): return refs
    def string(obj,key):
        if key not in obj: return '',False
        value=obj[key]
        if value is None: return '',True
        return (value,True) if isinstance(value,str) else ('',False)
    def obj(key):
        value=top.get(key)
        return value if isinstance(value,dict) else {}
    is_project=event_type.startswith(('project:','project_resource:'))
    if is_project:
        identity,valid=string(obj('project'),'id')
        if valid and identity: return EventRefs(project_known=True,project_id=identity)
    identity,valid=string(top,'project_id')
    if valid and identity and (is_project or event_type=='issue:deleted' or event_type in project_events):
        return EventRefs(project_known=True,project_id=identity)
    if event_type.startswith('autopilot:'):
        identity,valid=string(obj('autopilot'),'project_id')
        if valid: return EventRefs(project_known=True,project_id=identity)
        identity,valid=string(top,'autopilot_id')
        if valid and identity: return EventRefs(autopilot_id=identity)
    issue=obj('issue')
    identity,valid=string(issue,'project_id')
    if valid: return EventRefs(project_known=True,project_id=identity)
    refs.issue_id,_=string(issue,'id')
    if not refs.issue_id: refs.issue_id,_=string(top,'issue_id')
    if not refs.issue_id:
        comment=obj('comment')
        identity,valid=string(comment,'issue_id')
        if valid and identity: refs.issue_id=identity
        else: refs.comment_id,_=string(comment,'id')
    if not refs.issue_id and not refs.comment_id: refs.comment_id,_=string(top,'comment_id')
    if not refs.issue_id and not refs.comment_id:
        linked=top.get('linked_issue_ids')
        if isinstance(linked,list):
            # encoding/json continues after element type errors; a fresh []string
            # retains zero values at invalid/null positions even when error ignored.
            refs.linked_issue_ids=[value if isinstance(value,str) else '' for value in linked]
    return refs
