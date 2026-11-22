"""Temporary account denylist from Go internal/auth/temporary_disabled_users.go."""
from fastapi import HTTPException
from .profile_decode import go_trim_space

USER_IDS={'514492f7-b30f-4147-bd33-c0e8ce5d6d4f','1d542296-17c6-484a-9914-dcee589be116'}
EMAILS={'pdzzer68@embassybase.com','gtwtrox@mowan666.com'}


def reject_disabled(user_id, email=''):
    if go_trim_space(user_id).lower() in USER_IDS or go_trim_space(email).lower() in EMAILS:
        raise HTTPException(403,'account disabled')
