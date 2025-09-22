# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct


class GetInstrumentInfo(BaseParser):

    """
    01 08 04 0b 00 01 0b 00 0b 00

    00 24
    08 类别
    00 00 00 00
    26 00  数量  38 个
    01 00 未知

    In [8]: 11402/38
    Out[8]: 300.05263157894734

    In [9]: 11402%38
    Out[9]: 2

    """
    def setParams(self, start, count=100):
        pkg = bytearray.fromhex("01 04 48 67 00 01 08 00 08 00 f5 23")
        pkg.extend(struct.pack('<IH', start, count))
        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        pos = 0
        start, count = struct.unpack("<IH", body_buf[:6])
        pos += 6
        result = []
        for i in range(count):
            (category, market, unused_bytes, code_raw, name_raw, desc_raw) = \
                struct.unpack("<BB3s9s17s9s", body_buf[pos: pos+40])

            code = code_raw.decode("gbk", 'ignore')
            name = name_raw.decode("gbk", 'ignore')
            desc = desc_raw.decode("gbk", 'ignore')

            one = OrderedDict(
                [
                    ("category", category),
                    ("market", market),
                    ("code", code.rstrip("\x00")),
                    ("name", name.rstrip("\x00")),
                    ("desc", desc.rstrip("\x00")),
                ]
            )

            pos += 64
            result.append(one)

        return result

if __name__ == '__main__':
    from pytdx.exhq import TdxExHq_API
    api = TdxExHq_API()
    api.connect('121.14.110.210', 7727)
    ret = api.get_instrument_info(200, 100)
    print(ret)
