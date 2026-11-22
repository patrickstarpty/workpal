"""Compose relay modes before opening readers or replaying events."""
from dataclasses import dataclass

from .redis_relay import RedisRelay
from .relay_modes import DualWriteBroadcaster, MirroredRelay
from .sharded_config import ShardedConfig
from .sharded_relay import ShardedRelay


@dataclass(frozen=True)
class RelayBundle:
    relay: object
    broadcaster: DualWriteBroadcaster
    external_relay: ShardedRelay | None
    clients: tuple


def create_relay(hub, client_factory, *, mode='sharded', config=None,
                 daemon_runtime=None, wecom_outbound=None):
    """Clients remain caller-owned; start only after all sinks are registered."""
    if mode not in ('legacy', 'dual', 'sharded'):
        raise ValueError('Invalid realtime relay mode')
    config = (config or ShardedConfig()).with_defaults()
    clients = []
    def client(name):
        result = client_factory(name)
        clients.append(result)
        return result
    write = client('realtime-write')
    external = None
    if mode == 'legacy':
        relay = RedisRelay(hub, write, read_client=client('realtime-read'),
                           retention=config.retention_config())
    elif mode == 'dual':
        sharded_read = client('realtime-read-sharded')
        legacy_read = client('realtime-read-legacy')
        external = ShardedRelay(hub, write, read_client=sharded_read, config=config,
                                daemon_runtime=daemon_runtime, wecom_outbound=wecom_outbound)
        legacy = RedisRelay(hub, write, read_client=legacy_read,
                            retention=config.retention_config())
        relay = MirroredRelay(external, legacy)
    else:
        external = ShardedRelay(hub, write, read_client=client('realtime-read'), config=config,
                                daemon_runtime=daemon_runtime, wecom_outbound=wecom_outbound)
        relay = external
    return RelayBundle(relay, DualWriteBroadcaster(hub, relay), external, tuple(clients))
