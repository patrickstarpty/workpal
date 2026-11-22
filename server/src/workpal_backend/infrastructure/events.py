"""Synchronous domain event subscribers with per-listener failure isolation."""
import logging
from threading import RLock
logger=logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._lock=RLock()
        self._listeners={}
        self._global=[]

    def subscribe(self,event_type,callback):
        with self._lock:self._listeners.setdefault(event_type,[]).append(callback)

    def subscribe_all(self,callback):
        with self._lock:self._global.append(callback)

    def subscriber_count(self,event_type):
        with self._lock:return len(self._listeners.get(event_type,[]))

    def publish(self,event):
        with self._lock:callbacks=[*self._listeners.get(event.get('type',''),[]),*self._global]
        for callback in callbacks:
            # Go passes Event by value; its Payload map remains shared.
            try:callback(dict(event))
            except Exception:
                # Never include event contents or database parameters in logs.
                logger.error('Domain event subscriber failed: %s',event.get('type',''))
