import pytest
from workpal_backend.realtime.forwarding import forward_workspace_event
from workpal_backend.realtime.metrics import RealtimeMetrics


class Broadcaster:
    def __init__(self):self.calls=[]
    def broadcast_to_scope(self,*args):self.calls.append(args)
    def broadcast_to_workspace(self,*args):self.calls.append(args)
    def broadcast(self,*args):self.calls.append(args)


def test_private_event_records_once_even_with_zero_or_multiple_recipients():
    for recipients in [[], ['u','u','v']]:
        metrics = RealtimeMetrics()
        broadcaster = Broadcaster()
        forward_workspace_event({'type':'issue:updated','workspaceID':'w','payload':{}},broadcaster,
                                audience=lambda event:(recipients,True),metrics=metrics)
        assert metrics.snapshot()['events_sent_by_type'] == {'issue:updated':1}
        assert len(broadcaster.calls) == len(recipients)


def test_dropped_or_unserializable_events_do_not_increment():
    metrics = RealtimeMetrics()
    broadcaster = Broadcaster()
    for event in [{'type':'chat:message','workspaceID':'w','payload':{}},
                  {'type':'inbox:new','workspaceID':'w','payload':{}},
                  {'type':'issue:updated','payload':{}},
                  {'type':'issue:updated','workspaceID':'w','payload':object()}]:
        forward_workspace_event(event,broadcaster,metrics=metrics)
    assert metrics.snapshot()['events_sent_by_type'] == {}
    assert broadcaster.calls == []


def test_event_is_recorded_before_broadcaster_failure():
    class Broken(Broadcaster):
        def broadcast_to_workspace(self,*args):raise RuntimeError('unavailable')
    metrics = RealtimeMetrics()
    with pytest.raises(RuntimeError):
        forward_workspace_event({'type':'issue:updated','workspaceID':'w','payload':{}},Broken(),metrics=metrics)
    assert metrics.snapshot()['events_sent_by_type'] == {'issue:updated':1}
