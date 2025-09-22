# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct

"""
tradex 结果

﻿        7、查询分时...

时间    价格    均价    成交量  成交额
09:30   3706.199951     3706.199951     27      13336
09:31   3705.199951     3705.910400     11      13335
09:32   3704.600098     3705.473633     19      13328
09:33   3701.399902     3704.717041     13      13324
09:34   3700.800049     3704.556152     3       13323
09:35   3699.800049     3703.379395     24      13321
09:36   3695.800049     3702.544922     12      13319
09:37   3700.600098     3702.510010     2       13318
"""


class GetMinuteTimeData(BaseParser):

    def setParams(self, market, code):
        pkg = bytearray.fromhex("01 07 08 00 01 01 0c 00 0c 00 0b 24")
        code = code.encode("utf-8")
        pkg.extend(struct.pack('<B9s', market, code))
        self.send_pkg = pkg


    def parseResponse(self, body_buf):
        pos = 0
        market, code, num = struct.unpack('<B9sH', body_buf[pos: pos+12])
        pos += 12

        result = []
        for i in range(num):

            (raw_time, price, avg_price, volume, amount) = struct.unpack("<HffII", body_buf[pos: pos+18])
            pos += 18
            hour = raw_time // 60
            minute = raw_time % 60

            result.append(OrderedDict([
                ("hour", hour),
                ("minute", minute),
                ("price", price),
                ("avg_price", avg_price),
                ("volume", volume),
                ("open_interest", amount),
            ]))

        return result