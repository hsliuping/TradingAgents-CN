# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct
import datetime

class GetHistoryTransactionData(BaseParser):

    def setParams(self, market, code, date, start, count):
        # if type(code) is six.text_type:
        code = code.encode("utf-8")

        # if type(date) is (type(date) is six.text_type) or (type(date) is six.binary_type):
        #     date = int(date)

        # pkg1 = bytearray.fromhex('01 01 30 00 02 01 16 00 16 00 06 24 3b c8 33 01 1f 30 30 30 32 30 00 00 00 01 00 00 00 00 f0 00')
        pkg = bytearray.fromhex('01 01 30 00 02 01 16 00 16 00 06 24')
        pkg.extend(struct.pack("<IB9siH", date, market, code, start, count))
        self.send_pkg = pkg
        self.date = date

    def parseResponse(self, body_buf):

        pos = 0
        market, code, _, num = struct.unpack('<B9s4sH', body_buf[pos: pos + 16])
        pos += 16
        result = []
        for i in range(num):

            (raw_time, price, volume, zengcang, direction) = struct.unpack("<HIIiH", body_buf[pos: pos + 16])

            pos += 16
            year = self.date // 10000
            month = self.date % 10000 // 100
            day = self.date % 100
            hour = raw_time // 60
            minute = raw_time % 60
            second = direction % 10000
            nature = direction #### 为了老用户接口的兼容性，已经转换为使用 nature_value
            value = direction // 10000
            # 对于大于59秒的值，属于无效数值
            if second > 59:
                second = 0
            date = datetime.datetime(year, month, day, hour, minute, second)

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
                ("price", price),
                ("volume", volume),
                ("zengcang", zengcang),
                ("natrue_name", nature_name),
                ("nature_name", nature_name), #修正了nature_name的拼写错误(natrue), 为了保持兼容性，原有的natrue_name还会保留一段时间
                ("direction", direction),
                ("nature", nature),

            ]))

        return result


if __name__ == '__main__':

    from pytdx.exhq import TdxExHq_API

    api = TdxExHq_API()
    with api.connect('121.14.110.210', 7727):
        # print(api.to_df(api.get_history_transaction_data(4, 'SR61099D', 20171025))[["date","price","volume",'zengcang','nature','t1','t2']])

        print(api.to_df(api.get_history_transaction_data(47, 'IFL0', 20170811)))
        #print(api.to_df(api.get_history_transaction_data(31,  "01918", 20171026))[["date","price","volume",'zengcang','nature']])
        #api.to_df(api.get_history_transaction_data(47, 'IFL0', 20170810)).to_excel('//Users//wy//data//iflo.xlsx')