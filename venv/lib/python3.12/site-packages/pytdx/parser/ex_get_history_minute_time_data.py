# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct


class GetHistoryMinuteTimeData(BaseParser):

    def setParams(self, market, code, date):
        pkg = bytearray.fromhex("01 01 30 00 01 01 10 00 10 00 0c 24")
        code = code.encode("utf-8")
        pkg.extend(struct.pack("<IB9s", date, market, code))
        #pkg = bytearray.fromhex('01 01 30 00 01 01 10 00 10 00 0c 24 3b c8 33 01 2f 49 46 4c 30 00 38 ec 2d 00')
        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        #        print('测试', body_buf)
        #        fileobj = open("//Users//wy//data//a.bin", 'wb')  # make partfile
        #        fileobj.write(body_buf)  # write data into partfile
        #        fileobj.close()
        pos = 0
        market, code, _, num = struct.unpack('<B9s8sH', body_buf[pos: pos + 20])
        pos += 20
#        print(market, code.decode(), num)
        result = []
        for i in range(num):

            (raw_time, price, avg_price, volume, amount) = struct.unpack("<HffII", body_buf[pos: pos + 18])

            pos += 18
            hour = raw_time // 60
            minute = raw_time % 60

            result.append(OrderedDict([
                ("hour", hour),
                ("minute", minute),
                ("price", price),
                ("avg_price", avg_price),
                ("volume", volume),
                ("open_interest", amount),
            ]))

        return result


if __name__ == '__main__':
    from pytdx.exhq import TdxExHq_API
    api = TdxExHq_API()
    cmd = GetHistoryMinuteTimeData(api)
    cmd.setParams(8, "10000843", 20180811)
    print(cmd.send_pkg)
