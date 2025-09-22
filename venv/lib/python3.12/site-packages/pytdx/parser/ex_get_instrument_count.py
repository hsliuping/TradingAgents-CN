# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct

# bytearray(b'TDX_DS\x00\x00\x00\x00\x00\x1f\xdc\x00\x00\x01\x00\x00\x00=\x9c\x00\x00t\x00\x00\x00\x00\x00\x00\x00')
class GetInstrumentCount(BaseParser):

    def setup(self):
        self.send_pkg = bytearray.fromhex("01 03 48 66 00 01 02 00 02 00 f0 23")

    def parseResponse(self, body_buf):
        pos = 0
        (num,) = struct.unpack("<I", body_buf[19: 19+4])
        return num


