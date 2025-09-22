# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct
import six


class GetSecurityQuotesCmd(BaseParser):

    def setParams(self, all_stock):
        """
         :param all_stock: 一个包含 (market, code) 元组的列表， 如 [ (0, '000001'), (1, '600001') ]
         :return:
        """
        stock_len = len(all_stock)
        if stock_len <= 0:
            return False

        pkgdatalen = stock_len * 7 + 12

        values = (
            0x10c,
            0x02006320,
            pkgdatalen,
            pkgdatalen,
            0x5053e,
            0,
            0,
            stock_len,
        )

        pkg_header = struct.pack("<HIHHIIHH", *values)
        pkg = bytearray(pkg_header)
        for stock in all_stock:
            market, code = stock
            if type(code) is six.text_type:
                code = code.encode("utf-8")
            one_stock_pkg = struct.pack("<B6s", market, code)
            pkg.extend(one_stock_pkg)

        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        pos = 0
        pos += 2  # skip b1 cb
        (num_stock,) = struct.unpack("<H", body_buf[pos: pos + 2])
        pos += 2
        stocks = []

        for _ in range(num_stock):
            # print(body_buf[pos:])
            # b'\x00000001\x95\n\x87\x0e\x01\x01\x05\x00\xb1\xb9\xd6\r\xc7\x0e\x8d\xd7\x1a\x84\x04S\x9c<M\xb6\xc8\x0e\x97\x8e\x0c\x00\xae\n\x00\x01\xa0\x1e\x9e\xb3\x03A\x02\x84\xf9\x01\xa8|B\x03\x8c\xd6\x01\xb0lC\x04\xb7\xdb\x02\xac\x7fD\x05\xbb\xb0\x01\xbe\xa0\x01y\x08\x01GC\x04\x00\x00\x95\n'
            (market, code, active1) = struct.unpack(
                "<B6sH", body_buf[pos: pos + 9])
            pos += 9
            price, pos = get_price(body_buf, pos)
            last_close_diff, pos = get_price(body_buf, pos)
            open_diff, pos = get_price(body_buf, pos)
            high_diff, pos = get_price(body_buf, pos)
            low_diff, pos = get_price(body_buf, pos)
            # 不确定这里应该是用 get_price 跳过还是直接跳过4个bytes
            # if price == 0 and last_close_diff == 0 and open_diff == 0 and high_diff == 0 and low_diff == 0:
            #     # 这个股票当前应该无法获取信息, 这个时候，这个值一般是0 或者 100
            #     #reversed_bytes0 = body_buf[pos: pos + 1]
            #     #pos += 1
            #     # 感觉这里应该都可以用 get_price ，但是由于一次性改动影响比较大，所以暂时只针对没有行情的股票做改动
            #     reversed_bytes0, pos = get_price(body_buf, pos)
            # else:
            #     reversed_bytes0 = body_buf[pos: pos + 4]
            #     pos += 4
            reversed_bytes0, pos = get_price(body_buf, pos)
            # reversed_bytes0, pos = get_price(body_buf, pos)
            # 应该是 -price
            reversed_bytes1, pos = get_price(body_buf, pos)
            # print('reversed_bytes1:' + str(reversed_bytes1)  + ",price" + str(price))
            # assert (reversed_bytes1 == -price)
            vol, pos = get_price(body_buf, pos)
            cur_vol, pos = get_price(body_buf, pos)
            (amount_raw,) = struct.unpack("<I", body_buf[pos: pos + 4])
            amount = get_volume(amount_raw)
            pos += 4
            s_vol, pos = get_price(body_buf, pos)
            b_vol, pos = get_price(body_buf, pos)
            reversed_bytes2, pos = get_price(body_buf, pos)
            reversed_bytes3, pos = get_price(body_buf, pos)

            bid1, pos = get_price(body_buf, pos)
            ask1, pos = get_price(body_buf, pos)
            bid_vol1, pos = get_price(body_buf, pos)
            ask_vol1, pos = get_price(body_buf, pos)

            bid2, pos = get_price(body_buf, pos)
            ask2, pos = get_price(body_buf, pos)
            bid_vol2, pos = get_price(body_buf, pos)
            ask_vol2, pos = get_price(body_buf, pos)

            bid3, pos = get_price(body_buf, pos)
            ask3, pos = get_price(body_buf, pos)
            bid_vol3, pos = get_price(body_buf, pos)
            ask_vol3, pos = get_price(body_buf, pos)

            bid4, pos = get_price(body_buf, pos)
            ask4, pos = get_price(body_buf, pos)
            bid_vol4, pos = get_price(body_buf, pos)
            ask_vol4, pos = get_price(body_buf, pos)

            bid5, pos = get_price(body_buf, pos)
            ask5, pos = get_price(body_buf, pos)
            bid_vol5, pos = get_price(body_buf, pos)
            ask_vol5, pos = get_price(body_buf, pos)

            # (reversed_bytes4, reversed_bytes5, reversed_bytes6,
            #  reversed_bytes7, reversed_bytes8, reversed_bytes9,
            #  active2) = struct.unpack("<HbbbbHH", body_buf[pos: pos + 10])
            # pos += 10

            reversed_bytes4 = struct.unpack("<H", body_buf[pos:pos+2])
            pos += 2
            reversed_bytes5, pos = get_price(body_buf, pos)
            reversed_bytes6, pos = get_price(body_buf, pos)
            reversed_bytes7, pos = get_price(body_buf, pos)
            reversed_bytes8, pos = get_price(body_buf, pos)
            (reversed_bytes9, active2) = struct.unpack(
                "<hH", body_buf[pos: pos + 4])
            pos += 4

            one_stock = OrderedDict([
                ("market", market),
                ("code", code.decode("utf-8")),
                ("active1", active1),
                ("price", self._cal_price(price, 0)),
                ("last_close", self._cal_price(price, last_close_diff)),
                ("open", self._cal_price(price, open_diff)),
                ("high", self._cal_price(price, high_diff)),
                ("low", self._cal_price(price, low_diff)),
                ("servertime", self._format_time('%s' % reversed_bytes0)),
                ("reversed_bytes0", reversed_bytes0),
                ("reversed_bytes1", reversed_bytes1),
                ("vol", vol),
                ("cur_vol", cur_vol),
                ("amount", amount),
                ("s_vol", s_vol),
                ("b_vol", b_vol),
                ("reversed_bytes2", reversed_bytes2),
                ("reversed_bytes3", reversed_bytes3),
                ("bid1", self._cal_price(price, bid1)),
                ("ask1", self._cal_price(price, ask1)),
                ("bid_vol1", bid_vol1),
                ("ask_vol1", ask_vol1),
                ("bid2", self._cal_price(price, bid2)),
                ("ask2", self._cal_price(price, ask2)),
                ("bid_vol2", bid_vol2),
                ("ask_vol2", ask_vol2),
                ("bid3", self._cal_price(price, bid3)),
                ("ask3", self._cal_price(price, ask3)),
                ("bid_vol3", bid_vol3),
                ("ask_vol3", ask_vol3),
                ("bid4", self._cal_price(price, bid4)),
                ("ask4", self._cal_price(price, ask4)),
                ("bid_vol4", bid_vol4),
                ("ask_vol4", ask_vol4),
                ("bid5", self._cal_price(price, bid5)),
                ("ask5", self._cal_price(price, ask5)),
                ("bid_vol5", bid_vol5),
                ("ask_vol5", ask_vol5),
                ("reversed_bytes4", reversed_bytes4),
                ("reversed_bytes5", reversed_bytes5),
                ("reversed_bytes6", reversed_bytes6),
                ("reversed_bytes7", reversed_bytes7),
                ("reversed_bytes8", reversed_bytes8),
                ("reversed_bytes9", reversed_bytes9/100.0),  # 涨速
                ("active2", active2)
            ])
            stocks.append(one_stock)
        return stocks

    def _cal_price(self, base_p, diff):
        return float(base_p + diff)/100

    def _format_time(self, time_stamp):
        """
        format time from reversed_bytes0
        by using method from https://github.com/rainx/pytdx/issues/187
        """
        time = time_stamp[:-6] + ':'
        if int(time_stamp[-6:-4]) < 60:
            time += '%s:' % time_stamp[-6:-4]
            time += '%06.3f' % (
                int(time_stamp[-4:]) * 60 / 10000.0
            )
        else:
            time += '%02d:' % (
                int(time_stamp[-6:]) * 60 / 1000000
            )
            time += '%06.3f' % (
                (int(time_stamp[-6:]) * 60 % 1000000) * 60 / 1000000.0
            )
        return time


if __name__ == '__main__':
    from pytdx.hq import TdxHq_API
    api = TdxHq_API()
    with api.connect():
        #print(api.to_df(api.get_security_quotes([(0, '102672'), (0, '002672')])))
        print(api.to_df(api.get_security_quotes(
            [(0, '101612'), (0, '002672')])))
