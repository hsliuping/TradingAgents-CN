# coding=utf-8


from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct
import six

"""
Notice：，如果一个股票当天停牌，那天的K线还是能取到，成交量为0


param: category=9, market=0, stockcode=000001, start=0, count=10
send: 0c01086401011c001c002d0500003030303030310900010000000a0000000000000000000000
recv: b1cb74000c01086401002d05aa00aa000a006ec73301b28c011e3254a081ad4816d6984d6fc7330154ae0182024ab0a51d4978090c4e70c733015414285e8003bb488b59a64d71c73301140086015ec059274945cb154e74c73301006828724060f648ae0edc4d75c73301000a1e7c40f6da48a37dc24d76c7330100680ad0018052b748ad68a24d77c7330100680072a0f0a448f8b9914d78c733010054285ee0a48b48c294764d7bc733010aa401b8014a001def4874abd44d

"""

class GetSecurityBarsCmd(BaseParser):

    def setParams(self, category, market, code, start, count):
        if type(code) is six.text_type:
            code = code.encode("utf-8")

        self.category = category

        values = (
            0x10c,
            0x01016408,
            0x1c,
            0x1c,
            0x052d,
            market,
            code,
            category,
            1,
            start,
            count,
            0, 0, 0  # I + I +  H total 10 zero
        )

        pkg = struct.pack("<HIHHHH6sHHHHIIH", *values)
        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        pos = 0

        (ret_count,) = struct.unpack("<H", body_buf[0: 2])
        pos += 2

        klines = []

        pre_diff_base = 0
        for i in range(ret_count):
            year, month, day, hour, minute, pos = get_datetime(self.category, body_buf, pos)

            price_open_diff, pos = get_price(body_buf, pos)
            price_close_diff, pos = get_price(body_buf, pos)

            price_high_diff, pos = get_price(body_buf, pos)
            price_low_diff, pos = get_price(body_buf, pos)

            (vol_raw,) = struct.unpack("<I", body_buf[pos: pos + 4])
            vol = get_volume(vol_raw)

            pos += 4
            (dbvol_raw,) = struct.unpack("<I", body_buf[pos: pos + 4])
            dbvol = get_volume(dbvol_raw)
            pos += 4

            open = self._cal_price1000(price_open_diff, pre_diff_base)

            price_open_diff = price_open_diff + pre_diff_base

            close = self._cal_price1000(price_open_diff, price_close_diff)
            high = self._cal_price1000(price_open_diff, price_high_diff)
            low = self._cal_price1000(price_open_diff, price_low_diff)

            pre_diff_base = price_open_diff + price_close_diff

            #### 为了避免python处理浮点数的时候，浮点数运算不精确问题，这里引入了多余的代码

            kline = OrderedDict([
                ("open", open),
                ("close", close),
                ("high", high),
                ("low", low),
                ("vol", vol),
                ("amount", dbvol),
                ("year", year),
                ("month", month),
                ("day", day),
                ("hour", hour),
                ("minute", minute),
                ("datetime", "%d-%02d-%02d %02d:%02d" % (year, month, day, hour, minute))
            ])
            klines.append(kline)
        return klines

    def _cal_price1000(self, base_p, diff):
        return float(base_p + diff)/1000