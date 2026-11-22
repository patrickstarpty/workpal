import pytest
from workpal_backend.config import Settings
@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f'sqlite:///{tmp_path}/test.sqlite', redis_url='redis://127.0.0.1:1', redis_key_prefix='test:foundation:')


@pytest.fixture
def isolated_relay_redis_port():
    """Disposable Redis on an ephemeral loopback port; no shared service data."""
    import subprocess
    import time
    from uuid import uuid4
    import redis
    name = 'workpal-relay-test-' + uuid4().hex
    client = None
    started = False
    try:
        subprocess.run(['docker','run','--rm','--pull','never','-d','--name',name,
                        '-p','127.0.0.1::6379','redis:7.4.7',
                        'redis-server','--save','','--appendonly','no'],
                       check=True,capture_output=True,text=True,timeout=30)
        started = True
        address = subprocess.run(['docker','port',name,'6379/tcp'],check=True,
                                 capture_output=True,text=True,timeout=10).stdout.strip()
        port = int(address.rsplit(':',1)[1])
        client = redis.Redis(host='127.0.0.1',port=port,socket_connect_timeout=.2,socket_timeout=.2)
        deadline = time.monotonic()+10
        while True:
            try:
                client.ping()
                break
            except redis.RedisError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Isolated test Redis did not become ready')
                time.sleep(.05)
        yield port
    finally:
        if client is not None:
            client.close()
        cleanup = subprocess.run(['docker','rm','-f',name],capture_output=True,text=True,timeout=15)
        if started and cleanup.returncode and 'No such container' not in cleanup.stderr:
            raise RuntimeError(f'Could not remove isolated Redis test container {name}')
