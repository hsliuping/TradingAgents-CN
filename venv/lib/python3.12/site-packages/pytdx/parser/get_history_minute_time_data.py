# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct
import six

class GetHistoryMinuteTimeData(BaseParser):

    def setParams(self, market, code, date):
        """
        :param market: 0/1
        :param code: '000001'
        :param date: 20161201  类似这样的整型
        :return:
        """

        if (type(date) is six.text_type) or (type(date) is six.binary_type):
            date = int(date)

        if type(code) is six.text_type:
            code = code.encode("utf-8")

        pkg = bytearray.fromhex(u'0c 01 30 00 01 01 0d 00 0d 00 b4 0f')
        pkg.extend(struct.pack("<IB6s", date, market, code))
        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        pos = 0
        (num, ) = struct.unpack("<H", body_buf[:2])
        last_price = 0
        # 跳过了4个字节，实在不知道是什么意思
        pos += 6
        prices = []
        for i in range(num):
            price_raw, pos = get_price(body_buf, pos)
            reversed1, pos = get_price(body_buf, pos)
            vol, pos = get_price(body_buf, pos)
            last_price = last_price + price_raw
            price = OrderedDict(
                [
                    ("price", float(last_price)/100),
                    ("vol", vol)
                ]
            )
            prices.append(price)
        return prices
