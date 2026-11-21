"""Stored membership queries; no implicit authorization."""
from sqlalchemy import select
from .models import members

def membership(session, user_id, workspace_id):
    return session.execute(select(members).where(members.c.user_id == user_id, members.c.workspace_id == workspace_id)).mappings().one_or_none()
