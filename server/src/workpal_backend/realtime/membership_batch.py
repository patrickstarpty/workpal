"""Bounded, fresh membership lookup cohorts; no cache or in-flight joining."""
import asyncio
from dataclasses import dataclass


@dataclass
class _Request:
    identity: tuple
    result: asyncio.Future
    deadline: float

    def pending(self):
        return not self.result.done() and asyncio.get_running_loop().time() < self.deadline

    def finish(self, member):
        if not self.result.done():
            self.result.set_result(bool(member) and self.pending())


class MembershipBatcher:
    def __init__(self, lookup):
        self.lookup = lookup
        self._requests = asyncio.Queue(maxsize=256)
        self._slots = asyncio.Semaphore(4)
        self._collector = None
        self._jobs = set()
        self._closed = False

    async def authorize(self, identity):
        if self._closed:
            return False
        loop = asyncio.get_running_loop()
        request = _Request(identity, loop.create_future(), loop.time()+3)
        if self._collector is None:
            self._collector = asyncio.create_task(self._collect())
        try:
            async with asyncio.timeout_at(request.deadline):
                await self._requests.put(request)
                member = await request.result
                return bool(member) and loop.time() < request.deadline
        except TimeoutError:
            return False
        finally:
            if not request.result.done():
                request.result.cancel()

    async def _collect(self):
        batch = []
        try:
            while True:
                first = await self._requests.get()
                if not first.pending():
                    first.finish(False)
                    continue
                batch = [first]
                end = asyncio.get_running_loop().time()+.001
                while len(batch) < 256:
                    try:
                        async with asyncio.timeout_at(end):
                            request = await self._requests.get()
                    except TimeoutError:
                        break
                    if request.pending():
                        batch.append(request)
                    else:
                        request.finish(False)
                    if asyncio.get_running_loop().time() >= end:
                        break
                # A slot is a worker ready to receive the fixed cohort. There
                # is no additional buffered queue of database jobs.
                await self._slots.acquire()
                job = asyncio.create_task(self._check(batch))
                self._jobs.add(job)
                job.add_done_callback(lambda done, requests=batch: self._job_done(done, requests))
                batch = []
        finally:
            for request in batch:
                request.finish(False)

    async def _check(self, requests):
        try:
            live = []
            identities = []
            seen = set()
            for request in requests:
                if not request.pending():
                    request.finish(False)
                    continue
                live.append(request)
                if request.identity not in seen:
                    seen.add(request.identity)
                    identities.append(request.identity)
            if not live:
                return
            deadline = min(asyncio.get_running_loop().time()+2,
                           max(request.deadline for request in live))
            try:
                async with asyncio.timeout_at(deadline):
                    members = await self.lookup(identities)
                # A callback may suppress cancellation; never trust a result
                # produced after the query's deadline.
                if asyncio.get_running_loop().time() >= deadline:
                    members = {}
            except Exception:
                members = {}
            for request in live:
                request.finish(members.get(request.identity, False))
        finally:
            for request in requests:
                request.finish(False)

    def _job_done(self, task, requests):
        self._jobs.discard(task)
        self._slots.release()
        # Includes cancellation before the worker coroutine ever starts.
        for request in requests:
            request.finish(False)

    async def close(self):
        self._closed = True
        tasks = ([self._collector] if self._collector is not None else []) + list(self._jobs)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        while not self._requests.empty():
            self._requests.get_nowait().finish(False)
