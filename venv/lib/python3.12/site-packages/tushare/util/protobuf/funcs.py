
import pandas as pd
import numpy as np
from decimal import Decimal
from typing import Dict, List, Optional
from tushare.util.protobuf.response_pb2 import Response, DataFrame, ColumnDataInt, ColumnDataFloat, ColumnDataStr

types = {
    np.str: 'ColumnDataStr',
    'float': 'ColumnDataFloat',
    'int': 'ColumnDataInt'
}


def protobuf_parse(in_bytes: bytes) -> dict:
    obj = Response()
    obj.ParseFromString(in_bytes)

    g = globals()
    rs: dict = {}
    for item, field in zip(obj.data.items, obj.data.fields):
        a = g[field.type]()
        item.Unpack(a)
        rs[field.name] = a.values
    return {
        'code': obj.code,
        'msg': obj.msg,
        'has_more': obj.data.has_more,
        'data': pd.DataFrame(rs)
    }
