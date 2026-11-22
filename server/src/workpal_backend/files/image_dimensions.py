# Header decoding adapted from Go image/{png,jpeg,gif}; see GO_LICENSE.txt.
"""Read displayed dimensions without decoding or allocating image pixels."""
import struct
import zlib


def _png(data):
    offset, stage, depth, color = 8, 0, 0, 0
    size = None
    while offset + 8 <= len(data):
        length = int.from_bytes(data[offset:offset + 4], 'big')
        kind = data[offset + 4:offset + 8]
        offset += 8
        if kind == b'IDAT':
            return size if stage >= 2 else None
        if length > 0x7fffffff or offset + length + 4 > len(data):
            return None
        body = data[offset:offset + length]
        crc = int.from_bytes(data[offset + length:offset + length + 4], 'big')
        if zlib.crc32(body, zlib.crc32(kind)) != crc:
            return None
        offset += length + 4
        if kind == b'IHDR':
            if stage != 0 or length != 13:
                return None
            width, height, depth, color, compression, filter_method, interlace = struct.unpack('>IIBBBBB', body)
            allowed = {1: (0, 3), 2: (0, 3), 4: (0, 3), 8: (0, 2, 3, 4, 6), 16: (0, 2, 4, 6)}
            if (not 0 < width < 1 << 31 or not 0 < height < 1 << 31 or
                    width * height > ((1 << 63) - 1) // 8 or compression or filter_method or
                    interlace not in (0, 1) or color not in allowed.get(depth, ())):
                return None
            size = width, height
            stage = 1
            if color != 3:
                return size
        elif kind == b'PLTE':
            if stage != 1 or length % 3 or not 0 < length // 3 <= min(256, 1 << depth):
                return None
            stage = 2
        elif kind == b'tRNS':
            if stage != 2 or length > 256:
                return None
            return size
        elif kind == b'IEND':
            return None
    return None


def _gif(data):
    if len(data) < 13 or data[:6] not in (b'GIF87a', b'GIF89a'):
        return None
    if data[10] & 128 and len(data) < 13 + 3 * (1 << (1 + (data[10] & 7))):
        return None
    return struct.unpack('<HH', data[6:10])


def _sof(body):
    if len(body) not in (9, 15, 18) or body[0] != 8 or body[5] != (len(body) - 6) // 3:
        return None
    components = body[5]
    seen, sampling = set(), []
    for i in range(components):
        identifier, hv, table = body[6 + 3 * i:9 + 3 * i]
        h, v = hv >> 4, hv & 15
        if identifier in seen or table > 3 or h not in (1, 2, 4) or v not in (1, 2, 4):
            return None
        seen.add(identifier)
        if components == 3:
            if ((i == 0 and v == 4) or
                    (i == 1 and (sampling[0][0] % h or sampling[0][1] % v)) or
                    (i == 2 and sampling[1] != (h, v))):
                return None
        elif components == 4:
            if ((i == 0 and hv not in (0x11, 0x22)) or
                    (i in (1, 2) and hv != 0x11) or
                    (i == 3 and sampling[0] != (h, v))):
                return None
        sampling.append((h, v))
    return int.from_bytes(body[3:5], 'big'), int.from_bytes(body[1:3], 'big')


def _jpeg(data):
    offset, jfif, size = 2, False, None
    while offset + 2 <= len(data):
        while offset + 1 < len(data) and data[offset] != 255:
            offset += 1
        if offset + 1 >= len(data):
            return None
        marker = data[offset + 1]
        offset += 2
        if marker == 0:
            continue
        while marker == 255 and offset < len(data):
            marker = data[offset]
            offset += 1
        if marker == 217:
            return None  # DecodeConfig without SOS/JFIF fails before pixels exist.
        if 208 <= marker <= 215:
            continue
        if offset + 2 > len(data):
            return None
        length = int.from_bytes(data[offset:offset + 2], 'big') - 2
        offset += 2
        if length < 0:
            return None
        if marker == 218:
            return size  # Config decoder does not read the SOS payload.
        if offset + length > len(data):
            return None
        body = data[offset:offset + length]
        offset += length
        if marker in (192, 193, 194):
            if size is not None:
                return None
            size = _sof(body)
            if size is None or jfif:
                return size
        elif marker == 224:
            if length >= 5:
                jfif = body[:5] == b'JFIF\0'
        elif not (224 <= marker <= 239 or marker in (196, 219, 221, 254)):
            return None
    return None


def _tiff_orientation(data):
    if len(data) < 8 or data[:2] not in (b'II', b'MM'):
        return 1
    order = 'little' if data[:2] == b'II' else 'big'
    def number(offset, count):return int.from_bytes(data[offset:offset + count], order)
    if number(2, 2) != 42:
        return 1
    offset = number(4, 4)
    if offset < 8 or offset + 2 > len(data):
        return 1
    for i in range(number(offset, 2)):
        entry = offset + 2 + i * 12
        if entry + 12 > len(data):
            return 1
        if number(entry, 2) != 0x112:
            continue
        if number(entry + 2, 2) != 3 or number(entry + 4, 4) != 1:
            return 1
        value = number(entry + 8, 2)
        return value if 1 <= value <= 8 else 1
    return 1


def _jpeg_orientation(data):
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 255:
            break
        marker = data[offset + 1]
        if marker == 255:
            offset += 1
            continue
        if marker in (218, 217):
            break
        length = int.from_bytes(data[offset + 2:offset + 4], 'big')
        end = offset + 2 + length
        if length < 2 or end > len(data):
            break
        payload = data[offset + 4:end]
        if marker == 225 and payload.startswith(b'Exif\0\0'):
            return _tiff_orientation(payload[6:])
        offset = end
    return 1


def dimensions(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        size = _png(data)
    elif data.startswith(b'GIF8'):
        size = _gif(data)
    elif data.startswith(b'\xff\xd8'):
        size = _jpeg(data)
        if size and _jpeg_orientation(data) >= 5:
            size = size[1], size[0]
    else:
        return None
    return size if size and all(0 < value < 1 << 31 for value in size) else None
