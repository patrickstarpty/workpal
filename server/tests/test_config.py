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
