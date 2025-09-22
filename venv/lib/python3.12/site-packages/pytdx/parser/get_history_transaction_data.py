# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price, get_time
from collections import OrderedDict
import struct
import six

class GetHistoryTransactionData(BaseParser):

    def setParams(self, market, code, start, count, date):
        if type(code) is six.text_type:
            code = code.encode("utf-8")

        if type(date) is (type(date) is six.text_type) or (type(date) is six.binary_type):
            date = int(date)

        pkg = bytearray.fromhex(u'0c 01 30 01 00 01 12 00 12 00 b5 0f')
        pkg.extend(struct.pack("<IH6sHH", date, market, code, start, count))
        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        pos = 0
        (num, ) = struct.unpack("<H", body_buf[:2])
        pos += 2
        ticks = []

        # skip 4 bytes
        pos += 4

        last_price = 0
        for i in range(num):
            ### ?? get_time
            # \x80\x03 = 14:56

            hour, minute, pos = get_time(body_buf, pos)

            price_raw, pos = get_price(body_buf, pos)
            vol, pos = get_price(body_buf, pos)
            buyorsell, pos = get_price(body_buf, pos)
            _, pos = get_price(body_buf, pos)

            last_price = last_price + price_raw

            tick = OrderedDict(
                [
                    ("time", "%02d:%02d" % (hour, minute)),
                    ("price", float(last_price)/100),
                    ("vol", vol),
                    ("buyorsell", buyorsell),
                ]
            )

            ticks.append(tick)

        return ticks


if __name__ == '__main__':
    from pytdx.hq import TdxHq_API
    api = TdxHq_API()
    with api.connect():
        print(api.to_df(api.get_history_transaction_data(0, '000001', 0, 10, 20170811)))
