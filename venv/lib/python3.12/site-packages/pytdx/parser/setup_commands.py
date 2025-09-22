# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct


class SetupCmd1(BaseParser):
    def setup(self):
        self.send_pkg = bytearray.fromhex(u'0c 02 18 93 00 01 03 00 03 00 0d 00 01')

    def parseResponse(self, body_buf):
        return body_buf


class SetupCmd2(BaseParser):
    def setup(self):
        self.send_pkg = bytearray.fromhex(u'0c 02 18 94 00 01 03 00 03 00 0d 00 02')

    def parseResponse(self, body_buf):
        return body_buf


class SetupCmd3(BaseParser):

    def setup(self):
        self.send_pkg = bytearray.fromhex(u'0c 03 18 99 00 01 20 00 20 00 db 0f d5'
                                      u'd0 c9 cc d6 a4 a8 af 00 00 00 8f c2 25'
                                      u'40 13 00 00 d5 00 c9 cc bd f0 d7 ea 00'
                                      u'00 00 02')

    def parseResponse(self, body_buf):
        return body_buf