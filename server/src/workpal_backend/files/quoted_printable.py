# Copyright 2012 The Go Authors. All rights reserved.
# Adapted from Go mime/quotedprintable/reader.go; see GO_LICENSE.txt.
"""Go quoted-printable body decoding, including its permissive extensions."""


def _decode_line(whole, at_eof):
    result = bytearray()
    line = whole.rstrip(b'\r\n \t')
    if line.endswith(b'='):
        remainder = whole[len(line):].lstrip(b' \t')
        line = line[:-1]
        if not (remainder.startswith((b'\n', b'\r\n')) or
                (not remainder and line and at_eof)):
            raise ValueError('invalid bytes after quoted-printable soft break')
    elif whole.endswith(b'\n'):
        line += b'\r\n' if whole.endswith(b'\r\n') else b'\n'
    index = 0
    while index < len(line):
        byte = line[index]
        if byte == 61:
            pair = line[index + 1:index + 3]
            if len(pair) == 2 and all(c in b'0123456789abcdefABCDEF' for c in pair):
                result.append(int(pair, 16))
                index += 3
                continue
            if len(line) - index < 2 or line[index + 1] in (10, 13):
                raise ValueError('invalid quoted-printable escape')
        elif byte not in (9, 10, 13) and (byte < 32 or byte == 127):
            raise ValueError('invalid unescaped quoted-printable byte')
        result.append(byte)
        index += 1
    return bytes(result)


class QuotedPrintableDecoder:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data, *, final=False):
        self.buffer.extend(data)
        result = bytearray()
        while True:
            newline = self.buffer.find(b'\n')
            if newline >= 0:
                if newline + 1 > 4096:
                    raise ValueError('quoted-printable line exceeds reader buffer')
                whole = bytes(self.buffer[:newline + 1])
                del self.buffer[:newline + 1]
                result.extend(_decode_line(whole, False))
                continue
            if len(self.buffer) > 4096 or (len(self.buffer) == 4096 and not final):
                raise ValueError('quoted-printable line exceeds reader buffer')
            if final and self.buffer:
                result.extend(_decode_line(bytes(self.buffer), True))
                self.buffer.clear()
            return bytes(result)


def decode_quoted_printable(data):
    return QuotedPrintableDecoder().feed(data, final=True)
