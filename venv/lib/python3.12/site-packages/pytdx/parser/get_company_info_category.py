# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct
import six

class GetCompanyInfoCategory(BaseParser):

    def setParams(self, market, code):
        if type(code) is six.text_type:
            code = code.encode("utf-8")

        pkg = bytearray.fromhex(u'0c 0f 10 9b 00 01 0e 00 0e 00 cf 02')
        pkg.extend(struct.pack(u"<H6sI", market, code, 0))
        self.send_pkg = pkg
    """

    10 00 d7 ee d0 c2 cc e1 ca be 00 00 ..... 36 30 30 33 30 30 2e 74 78 74 .... e8 e3 07 00 92 1f 00 00 .....

    10.... name
    36.... filename

    e8 e3 07 00 --- start
    92 1f 00 00 --- length

    """
    def parseResponse(self, body_buf):
        pos = 0
        (num, ) = struct.unpack("<H", body_buf[:2])
        pos += 2

        category = []



        def get_str(b):
            p = b.find(b'\x00')
            if p != -1:
                b = b[0: p]
            try:
                n = b.decode("gbk")
            except Exception as e:
                n = "unkown_str"
            return n

        for i in range(num):
            (name, filename, start, length) = struct.unpack(u"<64s80sII", body_buf[pos: pos+ 152])
            pos += 152
            entry = OrderedDict(
                [
                    ('name', get_str(name)),
                    ('filename', get_str(filename)),
                    ('start', start),
                    ('length', length),
                ]
            )
            category.append(entry)

        return category

