# Copyright 2011 The Go Authors. All rights reserved.
# Adapted from Go net/http/sniff.go; see GO_LICENSE.txt for the BSD license.
"""Pinned Go content sniffing, followed by Workpal's upload extension overrides."""
from workpal_backend.workspaces.decode import go_lower

_HTML = (b'<!DOCTYPE HTML', b'<HTML', b'<HEAD', b'<SCRIPT', b'<IFRAME', b'<H1',
         b'<DIV', b'<FONT', b'<TABLE', b'<A', b'<STYLE', b'<TITLE', b'<B',
         b'<BODY', b'<BR', b'<P', b'<!--')
_OVERRIDES = {'.svg': 'image/svg+xml', '.css': 'text/css', '.js': 'application/javascript',
              '.mjs': 'application/javascript', '.json': 'application/json', '.wasm': 'application/wasm'}
_IMAGES = ((b'\x00\x00\x01\x00', 'image/x-icon'), (b'\x00\x00\x02\x00', 'image/x-icon'),
           (b'BM', 'image/bmp'), (b'GIF87a', 'image/gif'), (b'GIF89a', 'image/gif'))
_TAIL = ((b'\x00\x01\x00\x00', 'font/ttf'), (b'OTTO', 'font/otf'), (b'ttcf', 'font/collection'),
         (b'wOFF', 'font/woff'), (b'wOF2', 'font/woff2'), (b'\x1f\x8b\x08', 'application/x-gzip'),
         (b'PK\x03\x04', 'application/zip'), (b'Rar!\x1a\x07\x00', 'application/x-rar-compressed'),
         (b'Rar!\x1a\x07\x01\x00', 'application/x-rar-compressed'), (b'\x00asm', 'application/wasm'))


def detect_content_type(data):
    data = data[:512]
    trimmed = data.lstrip(b'\t\n\x0c\r ')
    for tag in _HTML:
        if len(trimmed) > len(tag) and trimmed[:len(tag)].upper() == tag and trimmed[len(tag)] in (32, 62):
            return 'text/html; charset=utf-8'
    if trimmed.startswith(b'<?xml'):
        return 'text/xml; charset=utf-8'
    for signature, mime in ((b'%PDF-', 'application/pdf'), (b'%!PS-Adobe-', 'application/postscript')):
        if data.startswith(signature):
            return mime
    if len(data) >= 4:
        if data.startswith(b'\xfe\xff'):
            return 'text/plain; charset=utf-16be'
        if data.startswith(b'\xff\xfe'):
            return 'text/plain; charset=utf-16le'
        if data.startswith(b'\xef\xbb\xbf'):
            return 'text/plain; charset=utf-8'
    for signature, mime in _IMAGES:
        if data.startswith(signature):
            return mime
    if len(data) >= 14 and data[:4] == b'RIFF' and data[8:14] == b'WEBPVP':
        return 'image/webp'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if len(data) >= 12 and data[:4] == b'FORM' and data[8:12] == b'AIFF':
        return 'audio/aiff'
    for signature, mime in ((b'ID3', 'audio/mpeg'), (b'OggS\x00', 'application/ogg'),
                            (b'MThd\x00\x00\x00\x06', 'audio/midi')):
        if data.startswith(signature):
            return mime
    if len(data) >= 12 and data[:4] == b'RIFF':
        if data[8:12] == b'AVI ':
            return 'video/avi'
        if data[8:12] == b'WAVE':
            return 'audio/wave'
    if len(data) >= 12:
        box_size = int.from_bytes(data[:4], 'big')
        if box_size <= len(data) and box_size % 4 == 0 and data[4:8] == b'ftyp':
            for start in range(8, box_size, 4):
                if start != 12 and data[start:start + 3] == b'mp4':
                    return 'video/mp4'
    if data.startswith(b'\x1a\x45\xdf\xa3'):
        return 'video/webm'
    if len(data) >= 36 and data[34:36] == b'LP':
        return 'application/vnd.ms-fontobject'
    for signature, mime in _TAIL:
        if data.startswith(signature):
            return mime
    if any(byte <= 8 or byte == 11 or 14 <= byte <= 26 or 28 <= byte <= 31 for byte in trimmed):
        return 'application/octet-stream'
    return 'text/plain; charset=utf-8'


def upload_content_type(data, filename):
    base = filename.rsplit('/', 1)[-1]
    dot = base.rfind('.')
    extension = go_lower(base[dot:]) if dot >= 0 else ''
    return _OVERRIDES.get(extension) or detect_content_type(data)
