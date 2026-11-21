from workpal_backend.workspaces.service import create_workspace, list_workspaces
from workpal_backend.auth.service import get_or_create_development_user
from workpal_backend.infrastructure.database import Database, migrate


def test_visibility(settings):
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        u = get_or_create_development_user(s, 'dev@workpal.local')['id']
        assert list_workspaces(s, u) == []
        w = create_workspace(s, u, ' Example ', ' Example ')
        assert list_workspaces(s, u) == [w]
        assert list_workspaces(s, 'other') == []
    db.close()

import pytest
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, func
from workpal_backend.workspaces.models import members, issue_status, workspaces
from workpal_backend.auth.models import users
from workpal_backend.workspaces.service import (
    require_workspace_access, remove_membership, WorkspaceValidationError,
    WorkspaceConflictError, WorkspaceAccessError, UnsupportedIdentityError,
)


def test_permissions_rollback_and_reopen(settings):
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        u = get_or_create_development_user(s, 'dev@workpal.local')['id']
        w = create_workspace(s, u, 'First', 'first-space')
        w2 = create_workspace(s, u, 'Second', 'second-space', ' xy ')
        assert [x['id'] for x in list_workspaces(s,u)] == [w['id'],w2['id']]
        assert w2['issue_prefix'] == 'XY'
        assert s.scalar(select(func.count()).select_from(issue_status)) == 14
        for slug in ('api','EN','a--b','','bad_slug'):
            with pytest.raises(WorkspaceValidationError): create_workspace(s,u,'Name',slug)
        with pytest.raises(WorkspaceConflictError): create_workspace(s,u,'Duplicate','FIRST-SPACE')
        with pytest.raises(WorkspaceAccessError): require_workspace_access(s,dict(user_id='other',identity_kind='session'),w['id'])
        with pytest.raises(UnsupportedIdentityError): require_workspace_access(s,dict(user_id=u,identity_kind='cloud'),w['id'])
        with pytest.raises(WorkspaceAccessError): require_workspace_access(s,dict(user_id=u,identity_kind='session'),'missing')
    with pytest.raises(RuntimeError):
        with db.transaction() as s:
            create_workspace(s,u,'Rollback','rollback-space')
            raise RuntimeError('injected after owner and statuses')
    db.close()
    db = Database(settings)
    with db.transaction() as s:
        assert len(list_workspaces(s,u)) == 2
        assert s.scalar(select(func.count()).select_from(issue_status)) == 14
        s.execute(users.insert().values(id='other',email='other@example.com',name='Other',created_at=w['created_at'],updated_at=w['updated_at']))
        s.execute(members.insert().values(id='other-member',workspace_id=w['id'],user_id='other',role='member',created_at=w['created_at']))
        remove_membership(s,dict(user_id=u,identity_kind='session'),w['id'],'other-member')
        with pytest.raises(WorkspaceAccessError): require_workspace_access(s,dict(user_id='other',identity_kind='session'),w['id'])
        s.execute(members.insert().values(id='other-owner',workspace_id=w['id'],user_id='other',role='owner',created_at=w['created_at']))
        owner = require_workspace_access(s,dict(user_id=u,identity_kind='session'),w['id'])['id']
    def leave(pair):
        uid, mid = pair
        try:
            with db.transaction() as s:
                remove_membership(s,dict(user_id=uid,identity_kind='session'),w['id'],mid)
            return 'removed'
        except WorkspaceValidationError:
            return 'guarded'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(leave,[(u,owner),('other','other-owner')])) == ['guarded','removed']
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(members).where(members.c.workspace_id == w['id'])) == 1
    db.close()
