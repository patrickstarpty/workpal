"""Dashboard aggregation over retained records; this module never creates runs."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


MAX_SAFE_INTEGER = 2 ** 53 - 1
ISSUE_REFERENCE = re.compile(r'\b[A-Z][A-Z0-9]*-\d+\b', re.ASCII)
WORKPAL_COAUTHOR = re.compile(
    r'^Co-authored-by:\s*Workpal\s*<workpal@users\.noreply\.github\.com>\s*$',
    re.IGNORECASE | re.MULTILINE,
)


def utc_now():
    return datetime.now(timezone.utc)


def timestamp(value):
    """Interpret unzoned ISO timestamps as UTC, retaining original strings in storage."""
    if not isinstance(value, str):
        raise ValueError('invalid timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


@dataclass(frozen=True)
class Filters:
    days: int
    timezone: ZoneInfo
    project_id: str | None
    today: date
    start: date


def filters(params, now):
    raw_days = params.get('days', '30')
    if not isinstance(raw_days, str) or not re.fullmatch(r'[0-9]{1,3}', raw_days):
        raise ValueError('days must be an integer between 1 and 365')
    days = int(raw_days)
    if not 1 <= days <= 365:
        raise ValueError('days must be an integer between 1 and 365')
    try:
        zone = ZoneInfo(params.get('tz') or 'UTC')
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        raise ValueError('tz must be a valid timezone') from None
    project_id = params.get('project_id') or None
    if project_id is not None and (not isinstance(project_id, str) or '\x00' in project_id):
        raise ValueError('invalid project_id')
    today = now.astimezone(zone).date()
    return Filters(days, zone, project_id, today, today - timedelta(days=days - 1))


def dashboard_rows(projects, issues, runs, path, params, now=None):
    selected = filters(params, now or utc_now())
    valid_projects = {project['id'] for project in projects}
    valid_issues = {issue['id'] for issue in issues}
    usage, failure, daily = '/usage/' in path, '/failures/' in path, path.endswith('/daily')
    fields = (
        ('input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens', 'task_count')
        if usage else ('task_count',) if failure
        else ('total_seconds', 'task_count', 'failed_count', 'cancelled_count')
    )
    grouped = {}
    for row in runs:
        if row.get('project_id') not in valid_projects or row.get('issue_id') not in valid_issues:
            continue
        if selected.project_id and row['project_id'] != selected.project_id:
            continue
        day = timestamp(row['completed_at']).astimezone(selected.timezone).date()
        if not selected.start <= day <= selected.today:
            continue
        dimensions = {'date': day.isoformat()} if daily else {'agent_id': row['agent_id']}
        if usage:
            dimensions.update(provider=row['provider'], model=row['model'])
        if failure:
            dimensions['failure_reason'] = row['failure_reason']
        key = tuple(dimensions.items())
        out = grouped.setdefault(key, dimensions)
        for field in fields:
            out[field] = out.get(field, 0) + row[field]
    return sorted(grouped.values(), key=lambda row: row['date'] if daily else row['agent_id'])


def safe_integer(value):
    return (
        type(value) in (int, float) and 0 <= value <= MAX_SAFE_INTEGER
        and (not isinstance(value, float) or (math.isfinite(value) and value.is_integer()))
    )


def validate_commits(rows):
    if not isinstance(rows, list) or len(rows) > 20_000:
        raise ValueError('Provide a JSON array of up to 20,000 commits.')
    result = []
    for row in rows:
        valid = isinstance(row, dict)
        if valid:
            valid = (
                all(isinstance(row.get(key), str) and row[key].strip() for key in ('repository', 'sha'))
                and isinstance(row.get('message'), str)
                and safe_integer(row.get('additions')) and safe_integer(row.get('deletions'))
                and safe_integer(row['additions'] + row['deletions'])
            )
        if valid:
            try:
                timestamp(row.get('at'))
            except (ValueError, OverflowError):
                valid = False
        if not valid:
            raise ValueError('Each commit needs repository, sha, message, at (ISO date), and non-negative integer additions and deletions.')
        explicit = 'agentLines' in row or 'humanLines' in row
        if explicit and not (
            safe_integer(row.get('agentLines')) and safe_integer(row.get('humanLines'))
            and row['agentLines'] + row['humanLines'] <= row['additions'] + row['deletions']
        ):
            raise ValueError('Agent and human line counts must be non-negative integers and cannot exceed total changes.')
        keys = ('repository', 'sha', 'message', 'at', 'additions', 'deletions')
        if explicit:
            keys += ('agentLines', 'humanLines')
        result.append({key: row[key] for key in keys})
    return result


def contribution(projects, issues, commits, params, now=None):
    now = now or utc_now()
    selected = filters(params, now)
    daily = [
        {'date': (selected.start + timedelta(days=day)).isoformat(),
         'commits': 0, 'agentLines': 0, 'humanLines': 0}
        for day in range(selected.days)
    ]
    calendar = {day['date']: day for day in daily}
    all_issues = {issue['id']: issue for issue in issues}
    valid_projects = {project['id'] for project in projects}
    matching_issues = {
        issue['identifier'].upper(): issue for issue in issues
        if issue.get('project_id') in valid_projects
        and (not selected.project_id or issue['project_id'] == selected.project_id)
    }
    totals = dict(commits=0, tickets=0, added=0, deleted=0, agentLines=0, humanLines=0)
    rows, seen, excluded = {}, set(), 0
    for commit in commits:
        try:
            at = timestamp(commit.get('at'))
        except (ValueError, OverflowError):
            continue
        if at > now:
            continue
        day = calendar.get(at.astimezone(selected.timezone).date().isoformat())
        if day is None:
            continue
        key = (commit['repository'], commit['sha'])
        if key in seen:
            continue
        seen.add(key)
        identifiers = dict.fromkeys(ISSUE_REFERENCE.findall(commit['message'].upper()))
        matches = [matching_issues[key] for key in identifiers if key in matching_issues]
        if not matches:
            excluded += 1
            continue
        total = commit['additions'] + commit['deletions']
        explicit = (safe_integer(commit.get('agentLines')) and safe_integer(commit.get('humanLines'))
                    and commit['agentLines'] + commit['humanLines'] <= total)
        remainder = total - (commit['agentLines'] + commit['humanLines'] if explicit else 0)
        agent_lines = (commit['agentLines'] if explicit else 0)
        if WORKPAL_COAUTHOR.search(commit['message']):
            agent_lines += remainder
        amounts = dict(commits=1, added=commit['additions'], deleted=commit['deletions'],
                       agentLines=agent_lines, humanLines=total - agent_lines)
        for field, value in amounts.items():
            totals[field] += value
        for field in ('commits', 'agentLines', 'humanLines'):
            day[field] += amounts[field]
        for issue in matches:
            if issue['id'] not in rows:
                ancestor, team, visited = issue, 'Unassigned', set()
                while ancestor and ancestor['id'] not in visited:
                    visited.add(ancestor['id'])
                    if ancestor.get('assignee_type') == 'squad':
                        team = ancestor['assignee_id']
                        break
                    ancestor = all_issues.get(ancestor.get('parent_issue_id'))
                rows[issue['id']] = dict(
                    id=issue['id'], identifier=issue['identifier'], title=issue['title'], team=team,
                    commits=0, added=0, deleted=0, agentLines=0, humanLines=0,
                )
            for field, value in amounts.items():
                rows[issue['id']][field] += value
    totals['tickets'] = len(rows)
    return dict(totals=totals, daily=daily, excluded=excluded,
                rows=sorted(rows.values(), key=lambda row: (-(row['added'] + row['deleted']), row['id'])))
