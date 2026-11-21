"""HTTP boundary expectations from contracts/batches/profile-update.md.

Avatar tests cover only the explicit bounded local policy, not external support.
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update, text
from workpal_backend.app import create_app
from workpal_backend.auth.models import users
from workpal_backend.infrastructure.database import migrate

FIELDS = ('name', 'avatar_url', 'language', 'profile_description', 'timezone')
SEED = dict(name='Original', avatar_url='https://example.invalid/existing.png',
            language='ja', profile_description='Existing description', timezone='Asia/Shanghai',
            onboarded_at='2025-01-02T03:04:05Z', onboarding_questionnaire={'answer': 'seed'},
            whats_new_seen_version='v9', star_prompt_shown_count=7,
            star_prompt_last_shown_at='2025-02-03T04:05:06Z',
            star_prompt_starred_at='2025-03-04T05:06:07Z',
            updated_at='2000-01-01T00:00:00Z',
            cloud_waitlist_email='private@example.com', cloud_waitlist_reason='Private interest')
IMMUTABLE = ('id', 'email', 'created_at', 'onboarded_at', 'onboarding_questionnaire',
             'whats_new_seen_version', 'star_prompt_shown_count',
             'star_prompt_last_shown_at', 'star_prompt_starred_at')


@pytest.fixture
def boundary(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        login = client.post('/auth/verify-code', json={'email': 'dev@workpal.local', 'code': '888888'})
        assert login.status_code == 200
        headers = {'Authorization': 'Bearer ' + login.json()['token']}
        uid = client.get('/api/me', headers=headers).json()['id']
        with client.app.state.database.transaction() as session:
            session.execute(update(users).where(users.c.id == uid).values(**SEED))
        def row():
            with client.app.state.database.transaction() as session:
                return dict(session.execute(select(users).where(users.c.id == uid)).mappings().one())
        before = row()
        yield client, headers, row, before
        with client.app.state.database.transaction() as session:
            assert session.execute(text('SELECT count(*) FROM outbox')).scalar_one() == 0


def success(boundary, patch=None, raw=None):
    client, headers, row, before = boundary
    response = client.patch('/api/me', headers=headers, **({'content': raw} if raw is not None else {'json': patch}))
    assert response.status_code == 200, response.text
    actual = response.json()
    stored = row()
    public_fields = set(IMMUTABLE) | set(FIELDS) | {'updated_at'}
    assert set(actual) == public_fields
    assert actual == {k: stored[k] for k in public_fields}
    for key in ('cloud_waitlist_email', 'cloud_waitlist_reason'):
        assert stored[key] == before[key]
    assert {k: actual[k] for k in IMMUTABLE} == {k: before[k] for k in IMMUTABLE}
    assert actual['updated_at'] != before['updated_at']
    return actual


@pytest.mark.parametrize('locale', ['en', 'zh-Hans', 'zh-Hant', 'ko', 'ja', 'fr', 'es', 'ru'])
def test_supported_locales(boundary, locale):
    assert success(boundary, {'language': ' ' + locale + ' '})['language'] == locale


@pytest.mark.parametrize('raw', ['{}', 'null', '{"unknown":{"name":"ignored"}}',
    json.dumps(dict.fromkeys(FIELDS)), *[json.dumps({field: None}) for field in FIELDS]])
def test_omitted_null_unknown_preserve_all_five_and_advance_timestamp(boundary, raw):
    actual = success(boundary, raw=raw)
    assert {k: actual[k] for k in FIELDS} == {k: SEED[k] for k in FIELDS}


@pytest.mark.parametrize('raw,field,want', [
    ('{"NAME":"Ada","name":null}', 'name', 'Original'),
    ('{"name":null,"NaMe":" Ada "}', 'name', 'Ada'),
    ('{"LANGUAGE":null,"language":"fr"}', 'language', 'fr'),
    ('{"TIMEZONE":"UTC","timezone":null}', 'timezone', 'Asia/Shanghai'),
    ('{"profile_deſcription":" folded "}', 'profile_description', 'folded'),
    ('{"tımezone":"invalid"}', 'timezone', 'Asia/Shanghai'),
])
def test_duplicate_and_folded_members_at_http_boundary(boundary, raw, field, want):
    assert success(boundary, raw=raw)[field] == want


@pytest.mark.parametrize('zone,want', [('UTC', 'UTC'), ('Local', 'Local'),
    ('Europe/Paris', 'Europe/Paris'), (' Asia/Shanghai ', 'Asia/Shanghai'), ('', None), (' \u3000 ', None)])
def test_timezone_values(boundary, zone, want):
    assert success(boundary, {'timezone': zone})['timezone'] == want


@pytest.mark.parametrize('value', ['猫' * 2000, '😀' * 2000, '\u3000猫\u0085', ' \x1c\x1d\x1e\x1f '])
def test_description_runes_and_go_trim(boundary, value):
    want = value.strip(' \u3000\u0085')
    assert success(boundary, {'profile_description': value})['profile_description'] == want


@pytest.mark.parametrize('patch,field,want', [
    ({'avatar_url': SEED['avatar_url']}, 'avatar_url', SEED['avatar_url']),
    ({'avatar_url': ' \u3000' + SEED['avatar_url'] + '\t'}, 'avatar_url', SEED['avatar_url']),
    ({'avatar_url': ''}, 'avatar_url', ''),
    ({'profile_description': ''}, 'profile_description', ''),
])
def test_unchanged_avatar_and_empty_clears(boundary, patch, field, want):
    assert success(boundary, patch)[field] == want


@pytest.mark.parametrize('patch,status,error', [
    ({'timezone': 'No/Such'}, 400, 'invalid timezone'),
    ({'profile_description': '猫' * 2001}, 400, 'profile_description exceeds 2000 characters'),
    ({'name': ' ', 'avatar_url': 'changed'}, 400, 'name is required'),
    ({'name': 'Changed', 'avatar_url': 'changed', 'language': 'invalid', 'profile_description': '猫' * 2001, 'timezone': 'bad'}, 501, 'Avatar updates are not supported'),
    ({'language': 'invalid', 'profile_description': '猫' * 2001, 'timezone': 'bad'}, 400, 'unsupported language'),
])
def test_rejections_are_atomic_and_ordered(boundary, patch, status, error):
    client, headers, row, before = boundary
    response = client.patch('/api/me', json=patch, headers=headers)
    assert (response.status_code, response.json()) == (status, {'error': error})
    assert row() == before


def test_authentication_csrf_bearer_and_revocation(boundary):
    client, headers, row, before = boundary
    csrf = client.cookies['workpal_csrf_session']
    for request_headers in ({}, {'X-CSRF-Token': 'wrong'}):
        response = client.patch('/api/me', json={'name': 'Rejected'}, headers=request_headers)
        assert (response.status_code, response.json()) == (403, {'error': 'Invalid CSRF token'})
        assert row() == before
    assert success(boundary, {'name': 'Bearer accepted'})['name'] == 'Bearer accepted'
    response = client.patch('/api/me', json={'name': 'Cookie accepted'}, headers={'X-CSRF-Token': csrf})
    assert response.status_code == 200
    assert response.json()['name'] == 'Cookie accepted'
    client.post('/auth/logout', headers=headers)
    revoked = row()
    response = client.patch('/api/me', json={'name': 'Rejected'}, headers=headers)
    assert (response.status_code, response.json()) == (401, {'error': 'Unauthorized'})
    assert row() == revoked
    client.cookies.clear()
    response = client.patch('/api/me', json={'name': 'Rejected'})
    assert (response.status_code, response.json()) == (401, {'error': 'Unauthorized'})
    assert row() == revoked


@pytest.mark.parametrize('field,value', [('name', 'Ada'), ('avatar_url', ''),
    ('language', 'fr'), ('profile_description', 'Replacement'), ('timezone', 'UTC')])
@pytest.mark.parametrize('null_last', [True, False])
def test_duplicate_null_string_order_for_each_field(boundary, field, value, null_last):
    members = [(field.upper(), value), (field, None)]
    if not null_last:
        members.reverse()
    raw = '{' + ','.join(json.dumps(k) + ':' + json.dumps(v) for k, v in members) + '}'
    assert success(boundary, raw=raw)[field] == (SEED[field] if null_last else value)
