# PEM framing follows Go encoding/pem; see ../files/GO_LICENSE.txt.
"""Parse the first valid PEM block, then require an RSA private key."""
import base64
import binascii
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _line(data, start):
    end = data.find(b'\n', start)
    if end < 0:
        return data[start:].rstrip(b' \t'), len(data)
    stop = end - 1 if end > start and data[end - 1] == 13 else end
    return data[start:stop].rstrip(b' \t'), end + 1


def _pem_der(data):
    position = 0
    while position < len(data):
        end = data.find(b'\n-----END ', position)
        if end < 0:
            break
        trailer = end + len(b'\n-----END ')
        begin = data.rfind(b'-----BEGIN ', position, end)
        position = trailer
        if begin < 0 or (begin > 0 and data[begin - 1] != 10):
            continue
        label, body_start = _line(data, begin + len(b'-----BEGIN '))
        if not label.endswith(b'-----'):
            continue
        label = label[:-5]
        headers = False
        while body_start < len(data):
            line, after = _line(data, body_start)
            if b':' not in line:
                break
            headers = True
            body_start = after
        if headers and body_start > end:
            continue
        expected = label + b'-----'
        if data[trailer:trailer + len(expected)] != expected:
            continue
        suffix, _ = _line(data, trailer + len(expected))
        if suffix:
            continue
        body = data[body_start:end] if end > body_start else b''
        body = body.translate(None, b' \t\r\n')
        try:
            return base64.b64decode(body, validate=True)
        except binascii.Error:
            continue
    raise ValueError('no PEM block found')


def parse_rsa_private_key(pem):
    try:
        key = serialization.load_der_private_key(_pem_der(pem), password=None)
    except (TypeError, ValueError) as error:
        raise ValueError('invalid RSA private key') from error
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError('PKCS8 key is not RSA')
    return key
