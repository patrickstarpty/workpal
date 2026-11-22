"""PostgreSQL JSONB decoded through Go encoding/json interface{} semantics."""
import json
import math
from decimal import Decimal


def decode_jsonb_value(raw):
    def number(raw):
        # JSONB normalizes an actual numeric zero, but a negative nonzero
        # decimal can still underflow to -0 when Go unmarshals into float64.
        if Decimal(raw).is_zero():return 0.0
        value=float(raw)
        return value if math.isfinite(value) else None
    def sorted_map(pairs):
        return dict(sorted(dict(pairs).items()))
    value=json.loads(raw,parse_int=number,parse_float=number,object_pairs_hook=sorted_map)
    # Go json.Unmarshal into any produces float64 numbers; JSON null maps to {}.
    if value is None:value={}
    return value
