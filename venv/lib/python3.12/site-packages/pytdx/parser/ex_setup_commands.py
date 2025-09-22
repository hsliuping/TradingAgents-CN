# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct


class ExSetupCmd1(BaseParser):

    def setup(self):
        self.send_pkg = bytearray.fromhex("01 01 48 65 00 01 52 00 52 00 54 24 1f 32 c6 e5"
                                            "d5 3d fb 41 1f 32 c6 e5 d5 3d fb 41 1f 32 c6 e5"
                                            "d5 3d fb 41 1f 32 c6 e5 d5 3d fb 41 1f 32 c6 e5"
                                            "d5 3d fb 41 1f 32 c6 e5 d5 3d fb 41 1f 32 c6 e5"
                                            "d5 3d fb 41 1f 32 c6 e5 d5 3d fb 41 cc e1 6d ff"
                                            "d5 ba 3f b8 cb c5 7a 05 4f 77 48 ea")

    def parseResponse(self, body_buf):
        pass