"""Mirrored Redis publishing and local-first dual-write delivery."""
import logging
from .relay_ids import make_ulid
from .relay_frame import inject_event_id

log = logging.getLogger(__name__)


class JoinedPublishError(Exception):
    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__('\n'.join(str(error) for error in errors))


class _Broadcaster:
    async def _send(self, scope, identity, exclude, frame):
        try:
            await self._publish_id(scope, identity, exclude, frame, self.id_factory())
        except Exception:
            pass

    async def broadcast_to_scope(self, scope, identity, frame):
        await self._send(scope, identity, '', frame)

    async def broadcast_to_workspace(self, workspace, frame):
        await self.broadcast_to_scope('workspace', workspace, frame)

    async def send_to_user(self, user, frame, *exclude_workspace):
        await self._send('user', user, exclude_workspace[0] if exclude_workspace else '', frame)

    async def broadcast(self, frame):
        await self._send('global', 'all', '', frame)


class MirroredRelay(_Broadcaster):
    def __init__(self, primary, mirror, *, metrics=None, id_factory=make_ulid):
        self.primary, self.mirror = primary, mirror
        self.metrics = metrics if metrics is not None else primary.metrics
        self.id_factory = id_factory

    @property
    def node_id(self):
        return self.primary.node_id

    def set_daemon_runtime_deliverer(self, deliverer):
        for relay in (self.primary, self.mirror):
            setter = getattr(relay, 'set_daemon_runtime_deliverer', None)
            if setter is not None:
                setter(deliverer)

    async def start(self, parent_stop):
        await self.primary.start(parent_stop)
        await self.mirror.start(parent_stop)
        self.metrics.node_id = self.node_id

    def stop(self):
        self.primary.stop()
        self.mirror.stop()

    async def wait(self):
        await self.primary.wait()
        await self.mirror.wait()

    async def publish_with_id(self, scope, identity, exclude, frame, event_id):
        primary_error = mirror_error = None
        try:
            await self.primary.publish_with_id(scope, identity, exclude, frame, event_id)
        except Exception as error:
            primary_error = error
        if scope == 'daemon_runtime':
            if primary_error is not None:
                raise primary_error
            return
        try:
            await self.mirror.publish_with_id(scope, identity, exclude, frame, event_id)
        except Exception as error:
            mirror_error = error
        if primary_error is not None:
            self.metrics.mirror_primary_errors += 1
            log.warning('realtime/redis mirror: primary publish failed: %s', primary_error)
        if mirror_error is not None:
            self.metrics.mirror_secondary_errors += 1
            log.warning('realtime/redis mirror: secondary publish failed: %s', mirror_error)
        if (primary_error is None) != (mirror_error is None):
            self.metrics.mirror_divergence_total += 1
            log.warning('realtime/redis mirror: divergent publish result')
        errors = [error for error in (primary_error, mirror_error) if error is not None]
        if errors:
            raise JoinedPublishError(errors)

    _publish_id = publish_with_id


class DualWriteBroadcaster(_Broadcaster):
    def __init__(self, local, relay, *, id_factory=make_ulid):
        self.local, self.relay = local, relay
        self.id_factory = id_factory

    async def _local_publish(self, scope, identity, exclude, frame, deliver):
        event_id = self.id_factory()
        deliver(inject_event_id(frame, event_id), event_id)
        try:
            await self.relay.publish_with_id(scope, identity, exclude, frame, event_id)
        except Exception:
            pass

    async def broadcast_to_scope(self, scope, identity, frame):
        await self._local_publish(scope, identity, '', frame,
            lambda raw, event_id: self.local.broadcast_to_scope(scope, identity, raw, event_id))

    async def send_to_user(self, user, frame, *exclude_workspace):
        exclude = exclude_workspace[0] if exclude_workspace else ''
        await self._local_publish('user', user, exclude, frame,
            lambda raw, event_id: self.local.send_to_user(user, raw, exclude, event_id))

    async def broadcast(self, frame):
        await self._local_publish('global', 'all', '', frame,
            lambda raw, event_id: self.local.broadcast_all(raw, '', event_id))
