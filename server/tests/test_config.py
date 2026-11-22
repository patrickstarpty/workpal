import pytest
from workpal_backend.config import Settings, ROOT

def test_mock_rejected():
    with pytest.raises(ValueError): Settings(database_url='sqlite:///server/data/workpal.sqlite')

def test_symlink_rejected(tmp_path):
    link = tmp_path/'alias'
    link.symlink_to(ROOT/'server/data/workpal.sqlite')
    with pytest.raises(ValueError): Settings(database_url=f'sqlite:///{link}')

@pytest.mark.parametrize('kwargs', [dict(dev_auth=True,host='0.0.0.0'),dict(dev_auth=True,environment='production')])
def test_dev_rejected(kwargs):
    with pytest.raises(ValueError): Settings(**kwargs)

@pytest.mark.parametrize('alias', ['direct','symlink','hardlink'])
def test_configured_mock_protected(tmp_path, monkeypatch, alias):
    import os
    mock = tmp_path/'mock.sqlite'
    mock.touch()
    monkeypatch.setenv('WORKPAL_DB',str(mock))
    target = tmp_path/'alias.sqlite'
    if alias == 'symlink': target.symlink_to(mock)
    elif alias == 'hardlink': os.link(mock,target)
    else: target = mock
    with pytest.raises(ValueError): Settings(database_url=f'sqlite:///{target}')

@pytest.mark.parametrize('relative', ['apps', 'server/src', 'server/data/mock', 'server/data/python', 'assets'])
def test_upload_rejects_repository_sources_and_mock_data(relative):
    with pytest.raises(ValueError):
        Settings(upload_dir=ROOT/relative)


def test_upload_protects_configured_mock_directory_alias(tmp_path, monkeypatch):
    mock = tmp_path/'mock'
    mock.mkdir()
    monkeypatch.setenv('WORKPAL_DB', str(mock/'state.sqlite'))
    alias = tmp_path/'alias'
    alias.symlink_to(mock, target_is_directory=True)
    with pytest.raises(ValueError):
        Settings(upload_dir=alias/'uploads')


def test_upload_accepts_dedicated_roots(tmp_path):
    assert Settings(upload_dir=tmp_path/'uploads').upload_dir == (tmp_path/'uploads').resolve()
    assert Settings().upload_dir == ROOT/'server/data/python/uploads'


def test_upstream_auth_environment_names_take_precedence(monkeypatch):
    monkeypatch.setenv('JWT_SECRET', 'upstream-test-key-' * 4)
    monkeypatch.setenv('AUTH_SECRET', 'legacy-test-key-' * 4)
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('WORKPAL_ENV', 'production')
    settings = Settings()
    assert settings.auth_secret == 'upstream-test-key-' * 4
    assert settings.environment == 'development'


def test_legacy_auth_environment_aliases_remain_usable(monkeypatch):
    monkeypatch.delenv('JWT_SECRET', raising=False)
    monkeypatch.delenv('APP_ENV', raising=False)
    monkeypatch.setenv('AUTH_SECRET', 'legacy-test-key-' * 4)
    monkeypatch.setenv('WORKPAL_ENV', 'development')
    assert Settings().auth_secret == 'legacy-test-key-' * 4
    assert Settings().environment == 'development'


@pytest.mark.parametrize('secret', [None, '', 'workpal-dev-secret-change-in-production',
                                    ' change-me-in-production '])
@pytest.mark.parametrize('environment', ['production', ' PRODUCTION '])
def test_production_refuses_upstream_insecure_secrets(secret, environment):
    with pytest.raises(ValueError, match='JWT_SECRET'):
        Settings(environment=environment, auth_secret=secret)


def test_go_development_secret_fallback_is_not_production_default():
    assert Settings(auth_secret=None).auth_secret == 'workpal-dev-secret-change-in-production'
    # Go's boot check rejects known placeholders, not all short strings.
    assert Settings(environment='production', auth_secret='fixture-custom-key').auth_secret == 'fixture-custom-key'
