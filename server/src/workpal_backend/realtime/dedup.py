"""Connection-local FIFO event IDs matching Go Client.markSeen."""
from collections import deque
from threading import Lock

class SeenEvents:
    def __init__(self):
        self._lock=Lock();self._ids=set();self._order=deque()
    def mark(self,event_id):
        if event_id=='':return True
        with self._lock:
            if event_id in self._ids:return False
            self._ids.add(event_id);self._order.append(event_id)
            if len(self._order)>128:self._ids.remove(self._order.popleft())
            return True
