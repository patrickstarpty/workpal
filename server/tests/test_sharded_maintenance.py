import asyncio


def test_missing_stream_resets_generation_and_repair_preserves_observation():
    from workpal_backend.realtime.sharded_publisher import ShardedPublisher
    from workpal_backend.realtime.sharded_maintenance import ShardedMaintenance
    from workpal_backend.realtime.sharded_config import ShardedConfig

    async def run():
        class Client:
            present = True
            async def exists(self, key): return self.present
            async def xtrim(self, key, **kwargs):
                assert kwargs == {'minid': '400000-0', 'approximate': False}
                return 2
            async def pttl(self, key): return -1
            async def pexpire(self, key, ttl): raise OSError('expiry failed')
            async def xlen(self, key): return 3
            async def info(self, section):
                return {'used_memory': 17, 'maxmemory': 19} if section == 'memory' else {'evicted_keys': 23}
        client = Client()
        publisher = ShardedPublisher(client, 'n', config=ShardedConfig(shards=1, enabled=True))
        maintenance = ShardedMaintenance(publisher, clock_ns=lambda: 1000_000_000_000)
        await maintenance.maintain_once()
        snapshot = publisher.metrics.snapshot()
        assert snapshot['streams'] == {'ws:relay:shard:0': {'entries': 3, 'pttl_millis': -1}}
        assert snapshot['streams_without_ttl'] == 1
        assert snapshot['retention_errors'] == 1
        assert snapshot['stream_trimmed_total'] == 2
        assert (snapshot['used_memory_bytes'], snapshot['max_memory_bytes'], snapshot['evicted_keys']) == (17, 19, 23)
        publisher.ttl.claim('ws:relay:shard:0', 1)
        client.present = False
        await maintenance.maintain_once()
        await maintenance.maintain_once()
        assert maintenance.generations == [1]
        assert publisher.seen == [False]
        assert publisher.metrics.stream_missing_total == 1
        assert publisher.metrics.streams_without_ttl == 0
        assert publisher.ttl.claim('ws:relay:shard:0', 1)
        assert publisher.metrics.snapshot()['streams']['ws:relay:shard:0'] == {'entries': 0, 'pttl_millis': -2}
    asyncio.run(run())


def test_cancelled_pass_preserves_previous_gauge_and_skips_commands():
    from workpal_backend.realtime.sharded_publisher import ShardedPublisher
    from workpal_backend.realtime.sharded_maintenance import ShardedMaintenance
    async def run():
        publisher = ShardedPublisher(object(), 'n')
        publisher.metrics.set_streams_without_ttl('sharded', 7)
        stop = asyncio.Event(); stop.set()
        await ShardedMaintenance(publisher).maintain_once(stop)
        assert publisher.metrics.streams_without_ttl == 7
        assert publisher.metrics.retention_errors == 0
    asyncio.run(run())
