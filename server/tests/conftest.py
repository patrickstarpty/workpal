import pytest
from workpal_backend.config import Settings
@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f'sqlite:///{tmp_path}/test.sqlite', redis_url='redis://127.0.0.1:1', redis_key_prefix='test:foundation:')
