# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct


"""
获取股票数量 深市

发送
0c 0c 18 6c 00 01 08 00 08 00 4e 04 00 00 75 c7 33 01


接收
Bc cb 74 00 0c 0c 18 6c 00 00 4e 04 02 00 02 00 e7 19

In [61]: 0x19e7
Out[61]: 6631


沪市

发送
0c 0c 18 6c 00 01 08 00 08 00 4e 04 01 00 75 c7 33 01

接收
Bc cb 74 00 0c 0c 18 6c 00 00 4e 04 02 00 02 00 b3 33

In [63]: 0x333b
Out[63]: 13115
"""

class GetSecurityCountCmd(BaseParser):

    def setParams(self, market):

        pkg = bytearray.fromhex(u"0c 0c 18 6c 00 01 08 00 08 00 4e 04")
        market_pkg = struct.pack("<H", market)
        pkg.extend(market_pkg)
        pkg.extend(b'\x75\xc7\x33\x01')
        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        (num, ) = struct.unpack("<H", body_buf[:2])
        return num
