# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price, get_time
from collections import OrderedDict
import struct
import six
import datetime

class GetTransactionData(BaseParser):

    def setParams(self, market, code, start, count):
        if type(code) is six.text_type:
            code = code.encode("utf-8")
        pkg = bytearray.fromhex('01 01 08 00 03 01 12 00 12 00 fc 23')
        pkg.extend(struct.pack("<B9siH", market, code, start, count))
        self.send_pkg = pkg

    def parseResponse(self, body_buf):

        pos = 0
        market, code, _, num = struct.unpack('<B9s4sH', body_buf[pos: pos + 16])
        pos += 16
        result = []
        for i in range(num):

            (raw_time, price, volume, zengcang, direction) = struct.unpack("<HIIiH", body_buf[pos: pos + 16])

            pos += 16
            hour = raw_time // 60
            minute = raw_time % 60
            second = direction % 10000
            nature = direction ### 保持老接口的兼容性

            if second > 59:
                second = 0

            date = datetime.datetime.combine(datetime.date.today(), datetime.time(hour,minute,second))

            value = direction // 10000

            if value == 0:
                direction = 1
                if zengcang > 0:
                    if volume > zengcang:
                        nature_name = "多开"
                    elif volume == zengcang:
                        nature_name = "双开"
                elif zengcang == 0:
                    nature_name = "多换"
                else:
                    if volume == -zengcang:
                        nature_name = "双平"
                    else:
                        nature_name = "空平"
            elif value == 1:
                direction = -1
                if zengcang > 0:
                    if volume > zengcang:
                        nature_name = "空开"
                    elif volume == zengcang:
                        nature_name = "双开"
                elif zengcang == 0:
                    nature_name = "空换"
                else:
                    if volume == -zengcang:
                        nature_name = "双平"
                    else:
                        nature_name = "多平"
            else:
                direction = 0
                if zengcang > 0:
                    if volume > zengcang:
                        nature_name = "开仓"
                    elif volume == zengcang:
                        nature_name = "双开"
                elif zengcang < 0:
                    if volume > -zengcang:
                        nature_name = "平仓"
                    elif volume == -zengcang:
                        nature_name = "双平"
                else:
                    nature_name = "换手"

            if market in [31,48]:
                if nature == 0:
                    direction = 1
                    nature_name = 'B'
                elif nature == 256:
                    direction = -1
                    nature_name = 'S'
                else: #512
                    direction = 0
                    nature_name = ''


            result.append(OrderedDict([
                ("date", date),
                ("hour", hour),
                ("minute", minute),
                ("second", second),
                ("price", price),
                ("volume", volume),
                ("zengcang", zengcang),
                ("nature", nature),
                ("nature_mark", nature // 10000),
                ("nature_value", nature % 10000),
                ("nature_name", nature_name),
                ("direction", direction),
            ]))

        return result


if __name__ == "__main__":
    from pytdx.exhq import TdxExHq_API

    api = TdxExHq_API()
    with api.connect('121.14.110.210', 7727):
        print(api.to_df(api.get_transaction_data(47, 'IFL9')))
        # print(api.to_df(api.get_transaction_data(31, "00020")))
