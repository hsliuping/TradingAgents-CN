    #coding=utf-8
from __future__ import unicode_literals, division

import pandas as pd
import os

import struct
from pytdx.reader.base_reader import TdxFileNotFoundException, TdxNotAssignVipdocPathException
from pytdx.reader.base_reader import BaseReader

"""
读取通达信数据
"""


class TdxExHqDailyBarReader(BaseReader):

    def __init__(self, vipdoc_path=None):
        self.vipdoc_path = vipdoc_path

    def parse_data_by_file(self, fname):

        if not os.path.isfile(fname):
            raise TdxFileNotFoundException('no tdx kline data, pleaes check path %s', fname)

        with open(fname, 'rb') as f:
            content = f.read()
            return self.unpack_records('<IffffIIf', content)


        return []


    def get_df(self, code_or_file):

        # 只传入了一个参数
        data = [self._df_convert(row) for row in self.parse_data_by_file(code_or_file)]

        df = pd.DataFrame(data=data, columns=('date', 'open', 'high', 'low', 'close', 'amount', 'volume','jiesuan', 'hk_stock_amount'))
        df.index = pd.to_datetime(df.date)
        return df[['open', 'high', 'low', 'close', 'amount', 'volume','jiesuan', 'hk_stock_amount']]

    def _df_convert(self, row):
        t_date = str(row[0])
        datestr = t_date[:4] + "-" + t_date[4:6] + "-" + t_date[6:]

        (hk_stock_amount, ) = struct.unpack('<f', struct.pack('<I', row[5]))
        new_row = (
            datestr,
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[7],
            hk_stock_amount
        )

        return new_row


if __name__ == '__main__':
    tdx_reader = TdxExHqDailyBarReader()
    try:
        print(tdx_reader.get_df("/Users/rainx/tmp/vipdoc/ds/29#A1801.day"))
        #print(tdx_reader.get_df("/Volumes/share/transfer/76#AG200.day"))

    except TdxFileNotFoundException as e:
        pass

