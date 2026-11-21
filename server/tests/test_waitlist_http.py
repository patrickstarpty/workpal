import pytest
from test_onboarding_json_edges import authenticated

@pytest.mark.parametrize('raw,status', [(b'{"email":"Name <A@example.com>"}',200),(b'{"email":"\\\"a b\\\"@example.com"}',200),(b'{"email":"a@example.com,b@example.com"}',400),(b'{"email":"a@example.com","email":null}',200),(b'{"email":42,"email":"a@example.com"}',400),(b'{}',400),(b' '*16385,413)])
def test_http(authenticated, raw, status):
    client, headers = authenticated
    response = client.post('/api/me/onboarding/cloud-waitlist',content=raw,headers=headers)
    assert response.status_code == status
    if status == 200:
        assert 'cloud_waitlist_email' not in response.json()
        assert response.json()['onboarded_at'] is None

@pytest.mark.parametrize('raw,error', [(b'null','email is required'),(b'{"email":"bad","reason":"'+b'x'*501+b'"}','email is invalid'), ('{"email":"a@example.com","reason":"'+'é'*251+'"}', 'reason is too long'),(b'{"email":"'+b'x'*255+b'"}', 'email is too long')])
def test_validation_order(authenticated, raw, error):
    client, headers = authenticated
    response = client.post('/api/me/onboarding/cloud-waitlist', content=raw, headers=headers)
    assert response.status_code == 400
    assert response.json() == {'error': error}


def test_auth_and_sql_failure(authenticated):
    from sqlalchemy import text
    client, headers = authenticated
    path = '/api/me/onboarding/cloud-waitlist'
    assert client.post(path, json={'email':'a@example.com'}).status_code == 403
    with client.app.state.database.transaction() as session:
        session.execute(text("CREATE TRIGGER reject_waitlist BEFORE UPDATE OF cloud_waitlist_email ON users BEGIN SELECT RAISE(ABORT, 'reject'); END"))
    response = client.post(path, json={'email':'a@example.com'}, headers=headers)
    assert response.status_code == 500
    assert response.json() == {'error':'failed to join waitlist'}


def test_lock_and_preservation(authenticated):
    import sqlite3
    from sqlalchemy import text
    client, headers = authenticated
    db = client.app.state.database
    path = '/api/me/onboarding/cloud-waitlist'
    raw = b'{"n":0.12345678901234567890123456789,"cloud_waitlist_email":"keep"}'
    with db.transaction() as session:
        session.execute(text('UPDATE users SET onboarding_questionnaire=:q'), {'q':raw})
    for _ in range(2):
        response = client.post(path,json={'email':' Name <A@example.com> ','reason':'  '},headers=headers)
        assert response.status_code == 200
        assert '0.12345678901234567890123456789' in response.text
    with db.transaction() as session:
        row = session.execute(text('SELECT * FROM users')).mappings().one()
        assert row['onboarding_questionnaire'] == raw
        assert row['cloud_waitlist_email'] == 'name <a@example.com>'
        assert row['cloud_waitlist_reason'] is None
    with sqlite3.connect(db.settings.database_url.removeprefix('sqlite:///')) as blocker:
        blocker.execute('BEGIN IMMEDIATE')
        try:
            assert client.post(path,json={'email':'b@example.com'},headers=headers).status_code == 503
        finally:
            blocker.rollback()
