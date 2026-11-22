"""Batch project references read by tasks; no database or model execution."""
import json
from ..auth.profile_decode import _Object,_replace_surrogates,_invalid_constant
from ..infrastructure.go_uuid import parse_uuid


def _context(raw):
    if isinstance(raw,bytes):raw=raw.decode('utf-8',errors='surrogateescape')
    if not isinstance(raw,str) or not raw:return None
    try:
        value=json.loads(_replace_surrogates(raw),object_pairs_hook=_Object,
                         parse_constant=_invalid_constant,parse_int=lambda _:0,parse_float=lambda _:0)
        if not isinstance(value,_Object):return None
        result={'TYPE':'','PROJECT_ID':'','PARENT_ISSUE_ID':''}
        for key,item in value:
            folded=''.join(c.upper() if 'a'<=c<='z' else 'S' if c=='ſ' else 'K' if c=='K' else c for c in key)
            if folded not in result:continue
            if item is None:continue
            if not isinstance(item,str):return None
            result[folded]=_replace_surrogates(item)
        return result if result['TYPE']=='quick_create' else None
    except (ValueError,RecursionError,UnicodeError):return None


def _optional_uuid(value):
    if value is None:return None
    return parse_uuid(value)


def tasks_projects(queries,tasks):
    projects=[None for _ in tasks];issues=[None for _ in tasks];runs=[None for _ in tasks]
    issue_set=set();run_set=set()
    for index,task in enumerate(tasks):
        if task.get('issue_id') is not None:issues[index]=parse_uuid(task['issue_id'])
        elif task.get('chat_session_id') is not None:continue
        elif task.get('autopilot_run_id') is not None:
            runs[index]=parse_uuid(task['autopilot_run_id']);run_set.add(runs[index])
        else:
            context=_context(task.get('context'))
            if context is None:continue
            try:projects[index]=[parse_uuid(context['PROJECT_ID'])]
            except ValueError:pass
            try:issues[index]=parse_uuid(context['PARENT_ISSUE_ID'])
            except ValueError:pass
        if issues[index] is not None:issue_set.add(issues[index])
    issue_projects={};run_projects={}
    if issue_set:
        for identity,project in queries.list_issue_project_ids(list(issue_set)):
            issue_projects[_optional_uuid(identity)]=_optional_uuid(project)
    if run_set:
        for identity,project in queries.list_autopilot_run_project_ids(list(run_set)):
            run_projects[_optional_uuid(identity)]=_optional_uuid(project)
    for index in range(len(tasks)):
        for project in (issue_projects.get(issues[index]),run_projects.get(runs[index])):
            if project is not None:
                if projects[index] is None:projects[index]=[]
                projects[index].append(project)
    return projects


def task_projects(queries,task):
    return tasks_projects(queries,[task])[0]
