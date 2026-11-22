"""Go injectEventID semantics without decoding raw payload numbers or trees."""
import json
from .frame_decode import _typed_layers
from ..auth.profile_decode import _Object,_replace_surrogates
from ..infrastructure.go_response import marshal_map_json

_SPACE=' \t\r\n'


def _skip_space(source,position):
    while position<len(source) and source[position] in _SPACE:position+=1
    return position


def _value_end(source,position):
    if source[position]=='"':return json.decoder.scanstring(source,position+1,True)[1]
    if source[position] not in '{[':
        while position<len(source) and source[position] not in _SPACE+',}':position+=1
        return position
    depth=0
    while position<len(source):
        char=source[position]
        if char=='"':position=json.decoder.scanstring(source,position+1,True)[1];continue
        if char in '{[':depth+=1
        elif char in '}]':
            depth-=1
            if depth==0:return position+1
        position+=1
    raise ValueError('incomplete JSON value')


def _compact(raw):
    output=[];quoted=False;escaped=False
    for char in raw:
        if quoted:
            output.append(char)
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
        elif char=='"':quoted=True;output.append(char)
        elif char not in _SPACE:output.append(char)
    value=''.join(output)
    return (value.replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
            .replace('\u2028','\\u2028').replace('\u2029','\\u2029')).encode('utf-8',errors='surrogateescape')


def _marshal_go_string(value):
    # Go distinguishes an invalid UTF-8 byte (escaped replacement) from a valid
    # U+FFFD rune (literal UTF-8). Surrogateescape retains that distinction.
    pieces=[b'"'];segment=[]
    for char in value:
        if 0xD800<=ord(char)<=0xDFFF:
            if segment:pieces.append(marshal_map_json(''.join(segment))[1:-1]);segment=[]
            pieces.append(b'\\ufffd')
        else:segment.append(char)
    if segment:pieces.append(marshal_map_json(''.join(segment))[1:-1])
    pieces.append(b'"')
    return b''.join(pieces)


def inject_event_id(frame,event_id):
    if not event_id or not frame or frame[0]!=ord('{'):return frame
    source=frame.decode('utf-8',errors='surrogateescape')
    try:
        parsed=_typed_layers(_replace_surrogates(source))
        if not isinstance(parsed,_Object):return frame
        values={};position=_skip_space(source,1)
        while source[position]!='}':
            key,position=json.decoder.scanstring(source,position+1,True)
            position=_skip_space(source,position)+1  # validated colon
            position=_skip_space(source,position);end=_value_end(source,position)
            values[_replace_surrogates(key)]=source[position:end]
            position=_skip_space(source,end)
            if source[position]==',':position=_skip_space(source,position+1)
        if 'event_id' in values:return frame
        encoded={key:_compact(value) for key,value in values.items()}
        encoded['event_id']=_marshal_go_string(event_id)
        return b'{'+b','.join(marshal_map_json(key)+b':'+encoded[key] for key in sorted(encoded))+b'}'
    except (ValueError,UnicodeError,IndexError):
        return frame
