import asyncio


def test_hub_subscription_and_disconnect_metrics_follow_room_transitions():
    from workpal_backend.realtime.hub import Hub, Connection
    async def run():
        class Socket:
            async def send_text(self, raw):pass
            async def close(self, code):pass
        hub = Hub()
        a,b = [Connection(Socket(),lambda:None,'w',u) for u in ['a','b']]
        try:
            hub.register(a);hub.register(b)
            hub.subscribe(a,'chat','c');hub.subscribe(b,'chat','c')
            assert not hub.subscribe(a,'chat','c')
            snapshot = hub.metrics.snapshot()
            assert (snapshot['connects_total'],snapshot['active_connections']) == (2,2)
            assert snapshot['subscribes_total'] == {'workspace':2,'user':2,'workspace_member':2,'chat':2}
            assert snapshot['active_scope_rooms'] == {'workspace':1,'user':2,'workspace_member':2,'chat':1}
            hub.broadcast_to_scope('chat','c',b'{}')
            await a.close()
            snapshot = hub.metrics.snapshot()
            assert snapshot['messages_sent_total'] == 2
            assert (snapshot['disconnects_total'],snapshot['active_connections']) == (1,1)
            assert snapshot['active_scope_rooms'] == {'workspace':1,'user':1,'workspace_member':1,'chat':1}
            assert snapshot['unsubscribes_total'] == {}
            hub.unsubscribe(b,'chat','c')
            assert hub.metrics.snapshot()['unsubscribes_total'] == {'chat':1}
            await b.close()
            assert all(n==0 for n in hub.metrics.snapshot()['active_scope_rooms'].values())
        finally:await hub.close()
    asyncio.run(run())


def test_event_counter_ignores_empty_and_snapshots_are_detached():
    from workpal_backend.realtime.metrics import RealtimeMetrics
    metrics = RealtimeMetrics()
    metrics.record_event('')
    metrics.record_event('task:created')
    metrics.record_event('task:created')
    metrics.add_scope('subscribe_denied_total','task',1)
    snapshot = metrics.snapshot()
    assert snapshot['events_sent_by_type'] == {'task:created':2}
    snapshot['subscribe_denied_total']['task'] = 90
    assert metrics.snapshot()['subscribe_denied_total']['task'] == 1
    metrics.reset()
    assert metrics.snapshot()['events_sent_by_type'] == {}


def test_repeated_registration_keeps_go_connection_counter_semantics():
    from workpal_backend.realtime.hub import Hub, Connection
    hub = Hub()
    connection = Connection(None,lambda:None,'w','u')
    hub.register(connection)
    hub.register(connection)
    snapshot = hub.metrics.snapshot()
    assert snapshot['connects_total'] == 2
    assert snapshot['active_connections'] == 2
    assert snapshot['subscribes_total'] == {'workspace':1,'user':1,'workspace_member':1}
    hub.unregister(connection)
    assert hub.metrics.snapshot()['active_connections'] == 1


def test_removal_queue_overflow_is_visible_in_hub_metrics():
    from workpal_backend.realtime.hub import Hub, Connection
    async def run():
        class Socket:
            async def close(self,code):pass
        async def check(workspace,user):
            await asyncio.Event().wait()
        hub = Hub(membership_check=check)
        hub.register(Connection(Socket(),lambda:None,'w','u'))
        try:
            for _ in range(65):
                hub.broadcast_to_scope('workspace','w',b'{"type":"member:removed","payload":{"workspace_id":"w","user_id":"u"}}')
            assert hub.removals.dropped == 1
            assert hub.metrics.snapshot()['membership_removals_dropped_total'] == 1
        finally:await hub.close()
    asyncio.run(run())
