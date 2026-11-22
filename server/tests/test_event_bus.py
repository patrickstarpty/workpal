"""Synchronous Go Bus semantics independent of database and transport choice."""
from workpal_backend.infrastructure.events import EventBus


def test_event_fields_are_copied_but_payload_is_shared():
    bus=EventBus();seen=[]
    event={'type':'agent:status','workspaceID':'workspace','payload':{'value':'old'}}
    def mutate(received):
        received['type']='changed';received['workspaceID']='other'
        received['payload']['value']='new'
    bus.subscribe('agent:status',mutate)
    bus.subscribe_all(lambda received:seen.append((received['type'],received['workspaceID'],received['payload']['value'])))
    bus.publish(event)
    assert seen==[('agent:status','workspace','new')]
    assert event['type']=='agent:status' and event['workspaceID']=='workspace'
    assert event['payload']['value']=='new'


def test_subscription_count_and_current_publish_snapshot():
    bus=EventBus();seen=[]
    def first(event):
        seen.append('first')
        bus.subscribe('x',lambda event:seen.append('late'))
        bus.subscribe_all(lambda event:seen.append('late-global'))
    bus.subscribe('x',first)
    bus.subscribe_all(lambda event:seen.append('global'))
    assert bus.subscriber_count('x')==1 and bus.subscriber_count('missing')==0
    bus.publish({'type':'x'})
    assert seen==['first','global'] and bus.subscriber_count('x')==2
    seen.clear();bus.publish({'type':'x'})
    assert seen==['first','late','global','late-global']


def test_failure_isolation_and_reentrant_order():
    bus=EventBus();seen=[]
    def failed(event):raise RuntimeError('fixture failure')
    def nested(event):
        seen.append('outer');bus.publish({'type':'nested'})
    bus.subscribe('x',failed);bus.subscribe('x',nested)
    bus.subscribe('nested',lambda event:seen.append('nested'))
    bus.subscribe_all(lambda event:seen.append('global:'+event['type']))
    bus.publish({'type':'x'})
    assert seen==['outer','nested','global:nested','global:x']
