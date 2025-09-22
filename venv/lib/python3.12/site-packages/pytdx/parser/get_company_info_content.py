# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct
import six


class GetCompanyInfoContent(BaseParser):

    def setParams(self, market, code, filename, start, length):
        if type(code) is six.text_type:
            code = code.encode("utf-8")

        if type(filename) is six.text_type:
            filename = filename.encode("utf-8")

        if len(filename) != 80:
            filename = filename.ljust(80, b'\x00')


        pkg = bytearray.fromhex(u'0c 07 10 9c 00 01 68 00 68 00 d0 02')
        pkg.extend(struct.pack(u"<H6sH80sIII", market, code, 0, filename, start, length, 0))
        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        pos = 0
        _, length = struct.unpack(u'<10sH', body_buf[:12])
        pos += 12
        content = body_buf[pos: pos+length]
        return content.decode("gbk")