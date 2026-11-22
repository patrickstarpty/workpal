import json
from workpal_backend.infrastructure.events import EventBus
from workpal_backend.realtime.metrics import RealtimeMetrics


class Broadcaster:
    def __init__(self):self.calls=[]
    def send_to_user(self,user,data,*exclude):self.calls.append(('user',user,exclude,json.loads(data)))
    def broadcast_to_workspace(self,workspace,data):self.calls.append(('workspace',workspace,(),json.loads(data)))
    def broadcast_to_scope(self,scope,identity,data):self.calls.append((scope,identity,(),json.loads(data)))
    def broadcast(self,data):self.calls.append(('global','',(),json.loads(data)))


def test_personal_and_dual_listeners_preserve_routing_order_and_metrics():
    from workpal_backend.realtime.listeners import register_listeners
    bus=EventBus();broadcaster=Broadcaster();metrics=RealtimeMetrics()
    register_listeners(bus,broadcaster,metrics=metrics)
    bus.publish(dict(type='inbox:new',workspaceID='w',payload={'item':{'recipient_id':'u'}}))
    bus.publish(dict(type='invitation:accepted',workspaceID='w',actorID='u',payload={}))
    assert [(scope,identity,exclude) for scope,identity,exclude,_ in broadcaster.calls] == [
        ('user','u',()),('user','u',('w',)),('workspace','w',())]
    assert metrics.snapshot()['events_sent_by_type'] == {'inbox:new':1,'invitation:accepted':2}
    assert bus.subscriber_count('inbox:new') == 1


def test_invitation_pointer_map_and_typed_response_are_distinct_from_plain_string():
    from workpal_backend.realtime.listeners import register_listeners
    from workpal_backend.realtime.event_payloads import StringPointer,InvitationResponse
    bus=EventBus();broadcaster=Broadcaster();metrics=RealtimeMetrics()
    register_listeners(bus,broadcaster,metrics=metrics)
    for invitation in [{'invitee_user_id':'ignored'}, {'invitee_user_id':StringPointer('pointer')},
                       InvitationResponse(id='i',invitee_user_id='typed'),InvitationResponse()]:
        bus.publish(dict(type='invitation:created',workspaceID='w',payload={'invitation':invitation}))
    assert [call[1] for call in broadcaster.calls] == ['pointer','typed']
    assert broadcaster.calls[1][3]['payload']['invitation']['id'] == 'i'
    assert 'inviter_name' not in broadcaster.calls[1][3]['payload']['invitation']
    assert metrics.snapshot()['events_sent_by_type'] == {'invitation:created':2}


def test_typed_member_dual_delivery_and_listener_failure_isolation():
    from workpal_backend.realtime.listeners import register_listeners
    from workpal_backend.realtime.event_payloads import MemberWithUserResponse
    bus=EventBus();broadcaster=Broadcaster();metrics=RealtimeMetrics()
    register_listeners(bus,broadcaster,metrics=metrics)
    bus.publish(dict(type='member:added',workspaceID='w',payload={'member':MemberWithUserResponse(user_id='u')}))
    assert [call[:3] for call in broadcaster.calls] == [('user','u',('w',)),('workspace','w',())]
    assert broadcaster.calls[0][3]['payload']['member']['avatar_url'] is None
    assert metrics.snapshot()['events_sent_by_type'] == {'member:added':2}


def test_personal_delivery_failure_does_not_skip_workspace_listener():
    from workpal_backend.realtime.listeners import register_listeners
    class Broken(Broadcaster):
        def send_to_user(self,*args):raise RuntimeError('unavailable')
    bus=EventBus();broadcaster=Broken();metrics=RealtimeMetrics()
    register_listeners(bus,broadcaster,metrics=metrics)
    bus.publish(dict(type='invitation:accepted',workspaceID='w',actorID='u',payload={}))
    assert [call[0] for call in broadcaster.calls] == ['workspace']
    assert metrics.snapshot()['events_sent_by_type'] == {'invitation:accepted':2}
