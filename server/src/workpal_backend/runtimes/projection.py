"""Public runtime response from Go handler/runtime.go; command previews are text only."""
import json
from workpal_backend.infrastructure.go_json_value import decode_jsonb_value
from workpal_backend.infrastructure.go_uuid import parse_uuid
from workpal_backend.infrastructure.sqlite_compat import timestamp_instant

LAUNCH_HEADERS = {'antigravity': 'agy -p (non-interactive)', 'claude': 'claude (stream-json)', 'codebuddy': 'codebuddy (stream-json)', 'codex': 'codex app-server', 'copilot': 'copilot (json)', 'cursor': 'cursor-agent (stream-json)', 'codearts': 'codearts run (json)', 'deveco': 'deveco run (json)', 'hermes': 'hermes acp', 'kimi': 'kimi acp', 'reasonix': 'reasonix acp', 'dsh': 'dsh --profile workpal (stdio)', 'kiro': 'kiro-cli acp', 'openclaw': 'openclaw agent (json)', 'opencode': 'opencode run (json)', 'pi': 'pi (json mode)', 'qoder': 'qodercli --acp', 'qoderclicn': 'qoderclicn --acp', 'traecli': 'traecli acp serve', 'grok': 'grok agent stdio', 'qwen': 'qwen -p (stream-json)', 'qwenpaw': 'qwenpaw acp', 'droid': 'droid exec (stream-json)', 'amp': 'amp --execute (stream-json)', 'dim': 'dim acp', 'devin': 'devin acp', 'mcode': 'mcode acp', 'muse': 'muse serve (msp)', 'zeroclaw': 'zeroclaw acp', 'museapp': 'museapp (remote receptionist)', 'zcode': 'zcode app-server', 'omp': 'omp (json mode)'}

def timestamp(value):
    if value is None:return None
    instant=timestamp_instant(value)
    return instant.isoformat(timespec='seconds').replace('+00:00','Z')


def public(row):
    metadata=decode_jsonb_value(row['metadata'])
    shared=json.loads(row['shared_with'])
    def flatten(values):
        for value in values:
            if isinstance(value,list):yield from flatten(value)
            else:yield parse_uuid(value) if value is not None else ''
    return dict(id=row['id'],workspace_id=row['workspace_id'],daemon_id=row['daemon_id'],
        name=row['name'],custom_name=row['custom_name'],runtime_mode=row['runtime_mode'],
        provider=row['provider'],launch_header=LAUNCH_HEADERS.get(row['provider'],''),
        status=row['status'],device_info=row['device_info'],metadata=metadata,
        owner_id=row['owner_id'],visibility=row['visibility'],shared_with=list(flatten(shared)),
        profile_id=row['profile_id'],max_concurrent_tasks=row['max_concurrent_tasks'],
        last_seen_at=timestamp(row['last_seen_at']),created_at=timestamp(row['created_at']),
        updated_at=timestamp(row['updated_at']))
