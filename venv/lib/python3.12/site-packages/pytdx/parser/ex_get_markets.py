# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct


class GetMarkets(BaseParser):

    def setup(self):
        self.send_pkg = bytearray.fromhex("01 02 48 69 00 01 02 00 02 00 f4 23")

    def parseResponse(self, body_buf):

        pos = 0
        (cnt, ) = struct.unpack("<H", body_buf[pos: pos + 2])
        pos += 2

        result = []
        for i in range(cnt):
            # 64byte for one
            (category, raw_name, market, raw_short_name, _, unknown_bytes) = struct.unpack("<B32sB2s26s2s", body_buf[pos: pos+64])
            pos += 64

            if category == 0 and market == 0:
                continue

            name = raw_name.decode("gbk")
            short_name = raw_short_name.decode("gbk")

            result.append(OrderedDict(
                [
                    ("market", market),
                    ("category", category),
                    ("name", name.rstrip("\x00")),
                    ("short_name", short_name.rstrip("\x00")),
                    #('unknown_bytes', unknown_bytes)
                ]
            ))

        return result


