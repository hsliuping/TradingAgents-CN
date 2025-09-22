# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct
import six
import sys


class GetReportFile(BaseParser):
    def setParams(self, filename, offset=0):
        pkg = bytearray.fromhex(u'0C 12 34 00 00 00')
        # Fom DTGear request.py file
        node_size = 0x7530
        raw_data = struct.pack(r"<H2I100s", 0x06B9,
                               offset, node_size, filename.encode("utf-8"))
        raw_data_len = struct.calcsize(r"<H2I100s")
        pkg.extend(struct.pack(u"<HH{}s".format(raw_data_len),
                               raw_data_len, raw_data_len, raw_data))
        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        (chunksize, ) = struct.unpack("<I", body_buf[:4])

        if chunksize > 0:
            return {
                "chunksize": chunksize,
                "chunkdata":  body_buf[4:]
            }
        else:
            return {
                "chunksize": 0
            }


if __name__ == "__main__":
    from pytdx.hq import TdxHq_API
    api = TdxHq_API()
    api.need_setup = False
    # calc.tdx.com.cn, calc2.tdx.com.cn
    with api.connect(ip="120.76.152.87"):
        # response = api.get_report_file(r"tdxfin/gpcw19980630.zip", 386003)
        content = api.get_report_file_by_size("tdxfin/gpcw.txt")
        # content = api.get_report_file_by_size("tdxfin/gpcw19980630.zip", 386073)
        print(content)
