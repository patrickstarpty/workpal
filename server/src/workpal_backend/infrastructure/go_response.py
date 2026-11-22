"""JSON framing and float64 notation used by Go handler.writeJSON."""
from decimal import Decimal
import json
import math
from json.encoder import _make_iterencode,encode_basestring
from starlette.responses import JSONResponse


def float64_text(value):
    if not math.isfinite(value):
        raise ValueError('non-finite JSON number')
    raw=repr(value)
    magnitude=abs(value)
    if magnitude==0:
        return '-0' if math.copysign(1,value)<0 else '0'
    if 1e-6<=magnitude<1e21:
        fixed=format(Decimal(raw),'f')
        return fixed.rstrip('0').rstrip('.') if '.' in fixed else fixed
    if 'e' in raw:
        base,exponent=raw.split('e')
        power=int(exponent)
        return base.removesuffix('.0')+'e'+('+' if power>=0 else '-')+str(abs(power))
    return raw.removesuffix('.0')


class GoJSONEncoder(json.JSONEncoder):
    def iterencode(self,value,_one_shot=False):
        # Python 3.11 is pinned by this application. Use its escaping/cycle
        # machinery but replace the float formatter, avoiding C encoder bypass.
        encode=_make_iterencode({} if self.check_circular else None,self.default,
            encode_basestring,self.indent,float64_text,self.key_separator,
            self.item_separator,self.sort_keys,self.skipkeys,_one_shot)
        return encode(value,0)


class GoJSONResponse(JSONResponse):
    def render(self,content):
        raw=json.dumps(content,cls=GoJSONEncoder,ensure_ascii=False,allow_nan=False,
                       separators=(',',':')).encode('utf-8')
        return (raw.replace(b'&',b'\\u0026').replace(b'<',b'\\u003c').replace(b'>',b'\\u003e')
            .replace('\u2028'.encode(),b'\\u2028').replace('\u2029'.encode(),b'\\u2029')+b'\n')


def marshal_map_json(content):
    """Go json.Marshal for JSON-shaped map values, without Encoder newline."""
    raw=json.dumps(content,cls=GoJSONEncoder,sort_keys=True,ensure_ascii=False,
                   allow_nan=False,separators=(',',':')).encode('utf-8')
    return (raw.replace(b'&',b'\\u0026').replace(b'<',b'\\u003c').replace(b'>',b'\\u003e')
        .replace('\u2028'.encode(),b'\\u2028').replace('\u2029'.encode(),b'\\u2029'))
