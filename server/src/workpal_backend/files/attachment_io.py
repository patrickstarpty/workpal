"""Run synchronous attachment storage off-loop and join owned I/O on cancel.

This adapter cannot interrupt a blocking storage syscall. The storage client
must supply its own I/O deadlines; cancellation waits for that call to return.
"""
import asyncio


async def _joined_call(operation, *args, dispose_on_cancel=None):
    task = asyncio.create_task(asyncio.to_thread(operation, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Shield alone leaves a detached worker behind. Repeated cancellation
        # must not allow the owner to close a handle while read/seek still runs.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except BaseException:
                break
        try:
            value = task.result()
        except BaseException:
            pass
        else:
            if dispose_on_cancel is not None:
                try:
                    await _joined_call(dispose_on_cancel, value)
                except BaseException:
                    pass
        raise


class AttachmentReader:
    def __init__(self, reader):
        self._reader = reader
        self.seekable = callable(getattr(reader, 'seek', None))

    async def read(self, size):
        return await _joined_call(self._reader.read, size)

    async def seek(self, offset, whence=0):
        return await _joined_call(self._reader.seek, offset, whence)

    async def close(self):
        # Go deferred Close ignores its error, but still releases the handle.
        try:
            await _joined_call(self._reader.close)
        except Exception:
            pass


async def open_attachment_reader(storage, key):
    raw = await _joined_call(storage.get_reader, key,
                             dispose_on_cancel=lambda reader: reader.close())
    return AttachmentReader(raw)
