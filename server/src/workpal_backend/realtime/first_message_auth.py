"""Decode the first-message auth struct before token authentication."""
from .frame_decode import _typed_layers, _fold
from ..auth.profile_decode import _Object, _replace_surrogates

_ERROR = 'expected auth message as first frame'


def decode_auth_message(raw):
    try:
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8', errors='surrogateescape')
        value = _typed_layers(_replace_surrogates(raw))
        if not isinstance(value, _Object):
            raise ValueError(_ERROR)
        kind = token = ''
        invalid = False
        for key, item in value:
            field = _fold(key)
            if item is None:
                continue
            if field == 'TYPE':
                if isinstance(item, str):
                    kind = _replace_surrogates(item)
                else:
                    invalid = True
            elif field == 'PAYLOAD':
                # Unlike RawMessage, a nested struct merges repeated objects;
                # null and absent token fields retain earlier assignments.
                if not isinstance(item, _Object):
                    invalid = True
                    continue
                for name, candidate in item:
                    if _fold(name) != 'TOKEN' or candidate is None:
                        continue
                    if isinstance(candidate, str):
                        token = _replace_surrogates(candidate)
                    else:
                        invalid = True
        if invalid or kind != 'auth' or not token:
            raise ValueError(_ERROR)
        return token
    except (TypeError, ValueError) as error:
        raise ValueError(_ERROR) from error


async def read_first_auth(ws, on_too_large=lambda: None):
    import asyncio
    from .protocol import MAX_FRAME_BYTES
    try:
        message = await asyncio.wait_for(ws.receive(), 10)
    except Exception:
        return '', 'auth timeout or read error', False
    if message['type'] == 'websocket.disconnect':
        if message.get('workpal.too_large'):
            on_too_large()
            return '', '', True
        return '', 'auth timeout or read error', False
    raw = message.get('text') or message.get('bytes') or b''
    if len(raw.encode() if isinstance(raw, str) else raw) > MAX_FRAME_BYTES:
        on_too_large()
        await ws.close(code=1009)
        return '', '', True
    try:
        return decode_auth_message(raw), '', False
    except ValueError:
        return '', _ERROR, False


async def send_auth_error(ws, detail):
    """Go writes the error once and closes the TCP connection even on failure."""
    try:
        await ws.send_json({'error': detail})
    finally:
        await abort_socket(ws)


async def abort_socket(ws):
    if 'workpal.websocket.abort' in ws.scope.get('extensions', {}):
        await ws.send({'type': 'websocket.close', 'workpal.abort': True})
    else:
        # Generic ASGI cannot request a TCP-only close.
        await ws.close(code=1008)
