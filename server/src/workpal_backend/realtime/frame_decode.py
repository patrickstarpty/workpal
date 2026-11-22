"""Go inboundFrame/subPayload typed JSON semantics for WebSocket messages."""
import json
import re
from ..auth.profile_decode import _Object,_replace_surrogates


_NUMBER=re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')


def _typed_layers(source):
    """Validate all JSON iteratively; retain only frame/subPayload object layers.

    Deeper values are unknown fields or invalid typed string values, so their
    contents are immaterial, but syntax and Go's nesting limit still apply.
    This avoids changing the process-wide recursion limit or building deep trees.
    """
    stack=[];root=None;have_root=False;position=0;size=len(source)
    def add(value):
        nonlocal root,have_root
        if not stack:
            root=value;have_root=True
            return
        frame=stack[-1]
        if frame['retain']:
            if frame['object']:frame['value'].append((frame['key'],value))
            else:frame['value'].append(value)
        frame['state']='comma'
    while True:
        while position<size and source[position] in ' \t\r\n':position+=1
        if not stack and have_root:
            if position!=size:raise ValueError('trailing JSON data')
            return root
        if position>=size:raise ValueError('incomplete JSON')
        char=source[position]
        if stack:
            frame=stack[-1];state=frame['state'];closing='}' if frame['object'] else ']'
            if state=='comma':
                if char==closing:stack.pop();position+=1;continue
                if char!=',':raise ValueError('expected JSON separator')
                frame['state']='key' if frame['object'] else 'value'
                position+=1;continue
            if state in ('first','key') and frame['object']:
                if state=='first' and char=='}':stack.pop();position+=1;continue
                if char!='"':raise ValueError('expected JSON key')
                frame['key'],position=json.decoder.scanstring(source,position+1,True)
                frame['state']='colon';continue
            if state=='colon':
                if char!=':':raise ValueError('expected JSON colon')
                frame['state']='value';position+=1;continue
            if state=='first' and char==']':stack.pop();position+=1;continue
        if char in '{[':
            if len(stack)>=10000:raise ValueError('JSON nesting exceeds Go limit')
            value=_Object() if char=='{' else []
            add(value)
            stack.append(dict(value=value,object=char=='{',retain=len(stack)<2,state='first',key=None))
            position+=1
        elif char=='"':
            value,position=json.decoder.scanstring(source,position+1,True);add(value)
        elif source.startswith('null',position):position+=4;add(None)
        elif source.startswith('true',position):position+=4;add(True)
        elif source.startswith('false',position):position+=5;add(False)
        else:
            number=_NUMBER.match(source,position)
            if number is None:raise ValueError('invalid JSON value')
            position=number.end();add(0)


def _fold(key):
    return ''.join(c.upper() if 'a'<=c<='z' else 'S' if c=='ſ' else 'K' if c=='K' else c for c in key)


def decode_frame(raw):
    if isinstance(raw,bytes):raw=raw.decode('utf-8',errors='surrogateescape')
    value=_typed_layers(_replace_surrogates(raw))
    if value is None:return '',None
    if not isinstance(value,_Object):raise ValueError('invalid frame')
    kind='';payload=None;invalid=False
    for key,item in value:
        field=_fold(key)
        if field=='TYPE':
            if item is None:continue
            if not isinstance(item,str):invalid=True
            else:kind=_replace_surrogates(item)
        elif field=='PAYLOAD':
            # json.RawMessage is replaced by each occurrence, including null.
            payload=item
    if invalid:raise ValueError('invalid frame type')
    return kind,payload


def decode_subscription(payload):
    scope='';identity='';invalid=False
    if payload is None:return scope,identity,False
    if not isinstance(payload,_Object):return scope,identity,False
    for key,item in payload:
        field=_fold(key)
        if field not in ('SCOPE','ID') or item is None:continue
        if not isinstance(item,str):invalid=True;continue
        item=_replace_surrogates(item)
        if field=='SCOPE':scope=item
        else:identity=item
    return scope,identity,bool(scope and identity and not invalid)
