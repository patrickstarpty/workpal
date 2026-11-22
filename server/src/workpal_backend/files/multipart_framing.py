# Portions adapted from Go mime/multipart. See GO_LICENSE.txt.
"""Streaming Go multipart boundary and MIME header framing.

Keeps body bytes unchanged in both CRLF and first-boundary LF modes.
"""


from starlette.concurrency import run_in_threadpool


class MultipartFramingError(ValueError):
    pass


class MultipartBodyLimit(MultipartFramingError):
    def __init__(self, limit):
        self.limit = limit


class _Buffer:
    def __init__(self, chunks, limit):
        self.chunks = chunks.__aiter__()
        self.limit = limit
        self.received = 0
        self.data = bytearray()
        self.error = None

    async def fill(self):
        if self.error is not None:
            return
        try:
            chunk = await anext(self.chunks)
        except StopAsyncIteration:
            self.error = EOFError()
            return
        remaining = self.limit - self.received
        self.data.extend(chunk[:remaining])
        self.received += min(len(chunk), remaining)
        if len(chunk) > remaining:
            self.error = MultipartBodyLimit(self.limit)

    async def line(self, max_length=None):
        while True:
            end = self.data.find(b'\n')
            if end >= 0:
                if max_length is not None and end + 1 > max_length:
                    raise MultipartFramingError('boundary line exceeds buffer')
                value = bytes(self.data[:end + 1])
                del self.data[:end + 1]
                return value, False
            if max_length is not None and len(self.data) >= max_length:
                raise MultipartFramingError('boundary line exceeds buffer')
            if self.error is not None:
                if not isinstance(self.error, EOFError):
                    raise self.error
                value = bytes(self.data)
                self.data.clear()
                return value, True
            await self.fill()


def _after_prefix(data, prefix, ended):
    if len(data) == len(prefix):
        return 1 if ended else 0
    byte = data[len(prefix)]
    if byte in (32, 9, 13, 10):
        return 1
    if byte == 45:
        if len(data) == len(prefix) + 1:
            return -1 if ended else 0
        if data[len(prefix) + 1] == 45:
            return 1
    return -1


def _scan(data, dash, newline_dash, total, ended):
    if total == 0:
        if data.startswith(dash):
            match = _after_prefix(data, dash, ended)
            return (len(dash), 'data') if match < 0 else (0, 'boundary' if match > 0 else 'more')
        if dash.startswith(data):
            return 0, 'error' if ended else 'more'
    index = data.find(newline_dash)
    if index >= 0:
        match = _after_prefix(data[index:], newline_dash, ended)
        return ((index + len(newline_dash), 'data') if match < 0 else
                (index, 'boundary' if match > 0 else 'more'))
    if newline_dash.startswith(data):
        return 0, 'error' if ended else 'more'
    index = data.rfind(newline_dash[:1])
    if index >= 0 and newline_dash.startswith(data[index:]):
        return index, 'data'
    return len(data), 'error' if ended else 'data'


def _header_name(value):
    return bool(value) and all(32 <= byte <= 126 and byte not in b'()<>@,;:\\"/[]?={}\t' for byte in value)


async def _headers(buffer, owner):
    lines = []
    while True:
        raw, ended = await buffer.line()
        if ended:
            raise MultipartFramingError('truncated headers')
        line = raw[:-2] if raw.endswith(b'\r\n') else raw[:-1]
        if not line:
            break
        if line[:1] in (b' ', b'\t'):
            if not lines:
                raise MultipartFramingError('initial header continuation')
            lines[-1] += b' ' + line.strip(b' \t')
        else:
            lines.append(line.rstrip(b' \t'))
            if len(lines) > owner.file_headers_remaining:
                raise MultipartFramingError('too many headers')
    for line in lines:
        name, colon, value = line.partition(b':')
        if not colon or not _header_name(name):
            raise MultipartFramingError('invalid header name')
        value = value.strip(b' \t')
        if any((byte < 32 and byte != 9) or byte == 127 for byte in value):
            raise MultipartFramingError('invalid header value')
        owner.on_header_field(name, 0, len(name))
        owner.on_header_value(value, 0, len(value))
        owner.on_header_end()
    owner.on_headers_finished()


async def _flush(owner):
    for part, data in owner._file_parts_to_write:
        if data and part.file._go_memory_limit == 0 and not part.file.file._rolled:
            await run_in_threadpool(part.file.file.rollover)
        await part.file.write(data)
    for part in owner._file_parts_to_finish:
        await part.file.seek(0)
    owner._file_parts_to_write.clear()
    owner._file_parts_to_finish.clear()


async def parse_framing(chunks, boundary, owner, body_limit):
    buffer = _Buffer(chunks, body_limit)
    dash = b'--' + boundary
    newline = b'\r\n'
    parts = 0
    while True:
        expect_part = False
        while True:
            line, ended = await buffer.line(4096)
            final = line.startswith(dash + b'--') and line[len(dash) + 2:].lstrip(b' \t') in (b'', newline)
            if final:
                owner.on_end()
                return
            if ended:
                raise MultipartFramingError('truncated boundary')
            if line.startswith(dash):
                rest = line[len(dash):].lstrip(b' \t')
                if parts == 0 and rest == b'\n':
                    newline = b'\n'
                if rest == newline:
                    break
            if expect_part:
                raise MultipartFramingError('expected next part')
            if parts == 0:
                continue
            if line == newline:
                expect_part = True
                continue
            raise MultipartFramingError('unexpected part separator')
        parts += 1
        owner.on_part_begin()
        await _headers(buffer, owner)
        total = 0
        while True:
            count, action = _scan(buffer.data, dash, newline + dash, total, buffer.error is not None)
            if count:
                data = bytes(buffer.data[:count])
                del buffer.data[:count]
                total += count
                owner.on_part_data(data, 0, len(data), final=action == 'boundary')
                await _flush(owner)
            if action == 'boundary':
                owner.on_part_end()
                await _flush(owner)
                break
            if action == 'error':
                if isinstance(buffer.error, MultipartBodyLimit):
                    raise buffer.error
                raise MultipartFramingError('truncated body')
            if not count:
                if buffer.error is not None or len(buffer.data) >= 4096:
                    raise MultipartFramingError('incomplete boundary')
                await buffer.fill()
