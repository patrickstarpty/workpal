"""Canonical upload form parsing and owned temporary-file cleanup.

Uses Go-compatible streaming framing and parameter/field policy.
This is not wired to the live upload route until the complete upload lifecycle
and remaining parser edge cases pass the contract gates.
"""
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from starlette.datastructures import Headers, UploadFile
from starlette.formparsers import MultiPartParser
from .mime_parameters import parse_media_type
from .form_values import query_is_invalid
from .quoted_printable import QuotedPrintableDecoder
from .multipart_framing import parse_framing, MultipartFramingError, MultipartBodyLimit

MAX_FILE_SIZE = 100 << 20
MAX_BODY_SIZE = MAX_FILE_SIZE + (1 << 20)
MAX_FORM_MEMORY = MAX_FILE_SIZE + (10 << 20)


class UploadFormError(ValueError):
    def __init__(self, status=400, detail='invalid multipart form', *, limit=None):
        super().__init__(detail)
        self.status, self.detail, self.limit = status, detail, limit


@dataclass
class UploadForm:
    values: dict
    files: dict

    def first_file(self):
        files = self.files.get('file', ())
        if not files:
            raise UploadFormError(400, 'missing file field: http: no such file')
        return files[0]

    def value(self, name):
        values = self.values.get(name, ())
        return values[0] if values else ''

    async def close(self):
        for files in self.files.values():
            for file in files:
                await file.close()


class _Parser(MultiPartParser):
    spool_max_size = MAX_FILE_SIZE

    def __init__(self):
        super().__init__(Headers(), None, max_part_size=MAX_BODY_SIZE)
        self.finished = False
        self.parts = 0
        self.file_headers_remaining = 10000
        self.file_memory_bytes = MAX_FILE_SIZE
        self.memory_bytes = MAX_FORM_MEMORY

    def on_part_begin(self):
        super().on_part_begin()
        self.parts += 1
        if self.parts > 1000:
            raise UploadFormError()
        self.part_size = 0
        self.decoder = None
        self.quoted = False
        self.skip = False

    def on_header_end(self):
        field = self._current_partial_header_name
        if b' ' not in field:
            field = field.lower()
        self._current_part.item_headers.append((field, self._current_partial_header_value))
        if len(self._current_part.item_headers) > 10000:
            raise UploadFormError()
        self._current_partial_header_name = b''
        self._current_partial_header_value = b''

    @staticmethod
    def header_size(headers):
        names = set()
        size = 0
        for key, value in headers:
            if key not in names:
                names.add(key)
                size += len(key) + 200
            size += len(value)
        return size

    def on_headers_finished(self):
        if self.header_size(self._current_part.item_headers) > self.memory_bytes:
            raise UploadFormError()
        first = {}
        for key, value in self._current_part.item_headers:
            first.setdefault(key, value)
        disposition, params, error = parse_media_type(first.get(b'content-disposition', b'').decode('utf8', 'surrogateescape'))
        name = params.get('name', '') if error is None and disposition == 'form-data' else ''
        self._current_part.field_name = name
        self.skip = not name
        if self.skip:
            return
        self.memory_bytes -= len(name.encode('utf8', 'surrogateescape')) + 200
        if self.memory_bytes < 0:
            raise UploadFormError()
        self.quoted = first.get(b'content-transfer-encoding', b'').lower() == b'quoted-printable'
        if self.quoted:
            self.decoder = QuotedPrintableDecoder()
            self._current_part.item_headers = [(k,v) for k,v in self._current_part.item_headers if k != b'content-transfer-encoding']
        filename = params.get('filename', '')
        if filename:
            self.memory_bytes -= 400 + self.header_size(self._current_part.item_headers) + 300
            if self.memory_bytes < 0:
                raise UploadFormError()
            filename = filename.rstrip('/').rsplit('/', 1)[-1] or '/'
            self.file_headers_remaining -= len(self._current_part.item_headers)
            if self.file_headers_remaining < 0:
                raise UploadFormError()
            file = SpooledTemporaryFile(max_size=self.file_memory_bytes)
            self._files_to_close_on_error.append(file)
            self._current_part.file = UploadFile(file, size=0, filename=filename,
                                                headers=Headers(raw=self._current_part.item_headers))
            self._current_part.file._go_memory_limit = self.file_memory_bytes

    def on_part_data(self, data, start, end, *, final=False):
        if self.skip:
            return
        if self.decoder is not None:
            try:
                data = self.decoder.feed(data[start:end], final=final)
            except ValueError as error:
                raise UploadFormError() from error
            start, end = 0, len(data)
        self._accept_data(data, start, end)

    def _accept_data(self, data, start, end):
        self.part_size += end - start
        if self._current_part.file is None:
            self.memory_bytes -= end - start
            if self.memory_bytes < 0:
                raise UploadFormError()
        super().on_part_data(data, start, end)

    def on_part_end(self):
        if self.skip:
            return
        if self.decoder is not None:
            try:
                tail = self.decoder.feed(b'', final=True)
            except ValueError as error:
                raise UploadFormError() from error
            self._accept_data(tail, 0, len(tail))
        if self._current_part.file is None:
            raw = bytes(self._current_part.data)
            self.items.append((self._current_part.field_name, raw.decode('utf8', 'surrogateescape')))
        else:
            if self.part_size <= self.file_memory_bytes:
                self.file_memory_bytes -= self.part_size
                self.memory_bytes -= self.part_size
            self._file_parts_to_finish.append(self._current_part)
            self.items.append((self._current_part.field_name, self._current_part.file))

    def on_end(self):
        self.finished = True


async def _chunks(body):
    if isinstance(body, bytes):
        for start in range(0, len(body), 4096):
            yield body[start:start + 4096]
    else:
        async for chunk in body:
            for start in range(0, len(chunk), 4096):
                yield chunk[start:start + 4096]


async def parse_upload_form(body, content_type, *, raw_query=b''):
    media, params, error = parse_media_type(content_type)
    if error is not None or media != 'multipart/form-data' or not params.get('boundary'):
        raise UploadFormError()
    owner = _Parser()
    try:
        await parse_framing(_chunks(body), params['boundary'].encode('utf8', 'surrogateescape'), owner, MAX_BODY_SIZE)
        values, files = {}, {}
        for name, value in owner.items:
            target = files if isinstance(value, UploadFile) else values
            target.setdefault(name, []).append(value)
        if query_is_invalid(raw_query):
            raise UploadFormError()
        if any(file.size > MAX_FILE_SIZE for file in files.get('file', ())):
            raise UploadFormError(413, 'file exceeds the 100 MiB upload limit', limit=MAX_FILE_SIZE)
        return UploadForm(values, files)
    except BaseException as error:
        for file in owner._files_to_close_on_error:
            file.close()
        if isinstance(error, MultipartBodyLimit):
            raise UploadFormError(413, 'file exceeds the 100 MiB upload limit', limit=error.limit) from error
        if isinstance(error, (MultipartFramingError, OSError)):
            raise UploadFormError() from error
        raise
