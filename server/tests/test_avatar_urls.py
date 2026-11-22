"""Avatar capabilities cannot be minted for arbitrary external storage URLs."""
from uuid import uuid4
import pytest


def test_local_round_trip_and_external_passthrough():
    from workpal_backend.files.avatar_urls import AvatarURLs,LocalObjectURLs
    policy=AvatarURLs('fixture-secret',LocalObjectURLs('https://files.example/'),'https://api.example///')
    key='users/member/avatar.PNG'
    raw='https://files.example/uploads/'+key
    resolved=policy.resolve(raw)
    assert resolved.startswith('https://api.example/api/avatars/')
    assert policy.key_from_served(resolved)==key
    assert policy.normalize(resolved)==raw
    assert policy.resolve(resolved)==resolved
    for external in ['https://other.example/uploads/'+key,'emoji:smile','data:image/png;base64,AAAA','https://files.example/uploads/avatar.svg']:
        assert policy.resolve(external)==external
    assert policy.key_from_served(resolved.replace('avatar.PNG','other.PNG')) is None
    assert AvatarURLs('rotated',policy.storage).key_from_served(resolved) is None


def test_publishability_rechecks_attachment_binding():
    from workpal_backend.files.avatar_urls import AvatarURLs,LocalObjectURLs
    policy=AvatarURLs('fixture-secret',LocalObjectURLs())
    aid=str(uuid4());key='workspaces/ws/'+aid+'.png'
    row={'content_type':'IMAGE/PNG'}
    lookup=lambda id:row if id==aid else None
    assert policy.publishable(key,lookup)
    row['comment_id']=str(uuid4())
    assert not policy.publishable(key,lookup)
    assert not policy.publishable('workspaces/ws/lark/image.png',lookup)
    assert not policy.publishable('users/member/image.svg',lookup)
    assert policy.publishable('users/member/image.png',lookup)


def test_accept_unchanged_and_reject_new_bound_upload():
    from workpal_backend.files.avatar_urls import AvatarURLs,LocalObjectURLs
    policy=AvatarURLs('fixture-secret',LocalObjectURLs())
    aid=str(uuid4());raw='/uploads/workspaces/ws/'+aid+'.png'
    assert policy.accept(' '+raw+' ',raw,lambda id:None)==raw
    with pytest.raises(ValueError,match='standalone image upload'):
        policy.accept(raw,'',lambda id:None)
    assert policy.accept('https://other.example/a.svg','',lambda id:None)=='https://other.example/a.svg'


def test_dot_extensions_and_redirect_cache():
    from workpal_backend.files.avatar_urls import content_type,redirect_max_age
    assert content_type('dir/.PNG')=='image/png'
    assert content_type('dir/x.png/')==''
    assert content_type('dir/x.svg')==''
    assert [redirect_max_age(t) for t in [0.5,1.9,2,119.9,120,999]]==[0,0,1,59,60,60]


def test_nonpositive_ttl_uses_go_default():
    from workpal_backend.files.avatar_urls import redirect_max_age
    assert redirect_max_age(0)==60
    assert redirect_max_age(-1)==60
