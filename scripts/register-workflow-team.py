"""Register sourced local role records without installing or executing skills.
Run with the same environment as the local Python service. Existing records are
preserved; repeated registration only inserts missing catalog identities.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from sqlalchemy import select
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.auth.models import users
from workpal_backend.workspaces.models import workspaces, members
from workpal_backend.workspace_content.repository import get_record, put_record


def register(slug='review'):
    settings = Settings()
    if not settings.dev_auth:
        raise RuntimeError('Registration requires local development authentication')
    db = Database(settings)
    root = Path(__file__).resolve().parents[1]
    data = root / 'apps/web/app/capabilities/data'
    roles = json.loads((data / 'role-profiles.json').read_text())
    squads = json.loads((data / 'squads.json').read_text())['squads']
    stamp = datetime.now(timezone.utc).isoformat()
    database = Path(db.engine.url.database)
    backup = database.with_name(database.name + '.before-workflow-team-' + datetime.now().strftime('%Y%m%d%H%M%S'))
    try:
        with sqlite3.connect(database) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        with db.transaction() as session:
            owner = session.execute(select(users).where(users.c.email == 'workpal@fwd.com')).mappings().one()
            workspace = session.execute(select(workspaces).where(workspaces.c.slug == slug)).mappings().one()
            membership = session.execute(select(members).where(members.c.workspace_id == workspace['id'], members.c.user_id == owner['id'])).mappings().one()
            if membership['role'] not in ('owner', 'admin'):
                raise RuntimeError('Demo account must administer the target workspace')
            def insert(kind, body):
                if get_record(session, workspace['id'], kind, body['id']) is None:
                    put_record(session, workspace['id'], kind, body)
            common = dict(workspace_id=workspace['id'], created_at=stamp, updated_at=stamp, creator_id=owner['id'], avatar_url=None, archived_at=None, archived_by=None)
            for role in roles:
                instructions = '\n\n'.join([role['mission'], 'Inputs: '+role['input'], 'Outputs: '+role['output'], 'Scope: '+role['scope'], 'Human decision: '+role['approval'], role['basis'], 'Source: '+role['sourceUrl']])
                insert('agents', dict(common, id='workflow-'+role['id'], avatar_url=role['avatarUrl'], name=role['name'], role=role['name'], description=role['mission'], instructions=instructions, owner_id=owner['id'], status='offline', runtime_id=None, runtime_bound=False, runtime_availability='offline', runtime_config={}, custom_args=[], model='', permission_mode='public', invocation_targets=[], max_concurrent_tasks=1, conversation_starters=[], skills=[], metadata=dict(source_author=role['sourceAuthor'], source_url=role['sourceUrl'], suggested_skill_ids=role['skills'], catalog_role_id=role['id'])))
            by_name = {r['name']:r for r in roles}
            for squad in squads:
                leader = 'workflow-'+by_name[squad['lead']]['id']
                ids = list(dict.fromkeys([leader]+['workflow-'+r for r in squad['core']+squad['specialists']]))
                insert('squads', dict(common, id='workflow-'+squad['id'], name=squad['name'], description=squad['mission'], instructions=squad['output']+'\n\n'+squad['humanDecision'], leader_id=leader, member_count=len(ids), member_preview=[dict(member_id=id, member_type='agent', role='leader' if id==leader else 'member') for id in ids]))
        print(json.dumps(dict(roles=len(roles), squads=len(squads), backup=str(backup))))
    finally:
        db.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='review')
    register(parser.parse_args().workspace)
