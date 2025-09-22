#coding: utf-8
import struct
from pytdx.reader.base_reader import BaseReader
from collections import OrderedDict
import pandas as pd
import os
from io import BytesIO

"""
参考这个 http://blog.csdn.net/Metal1/article/details/44352639

"""

BlockReader_TYPE_FLAT = 0
BlockReader_TYPE_GROUP = 1

class BlockReader(BaseReader):

    def get_df(self, fname, result_type=BlockReader_TYPE_FLAT):
        result = self.get_data(fname, result_type)
        return pd.DataFrame(result)

    def get_data(self, fname, result_type=BlockReader_TYPE_FLAT):

        result = []

        if type(fname) is not bytearray:
            with open(fname, "rb") as f:
                data = f.read()
        else:
            data = fname

        pos = 384
        (num, ) = struct.unpack("<H", data[pos: pos+2])
        pos += 2
        for i in range(num):
            blockname_raw = data[pos: pos+9]
            pos += 9
            blockname = blockname_raw.decode("gbk", 'ignore').rstrip("\x00")
            stock_count, block_type = struct.unpack("<HH", data[pos: pos+4])
            pos += 4
            block_stock_begin = pos
            codes = []
            for code_index in range(stock_count):
                one_code = data[pos: pos+7].decode("utf-8", 'ignore').rstrip("\x00")
                pos += 7

                if result_type == BlockReader_TYPE_FLAT:
                    result.append(
                        OrderedDict([
                            ("blockname", blockname),
                            ("block_type", block_type),
                            ("code_index", code_index),
                            ("code", one_code),
                        ])
                    )
                elif result_type == BlockReader_TYPE_GROUP:
                    codes.append(one_code)

            if result_type == BlockReader_TYPE_GROUP:
                result.append(
                    OrderedDict([
                        ("blockname", blockname),
                        ("block_type", block_type),
                        ("stock_count", stock_count),
                        ("code_list", ",".join(codes))
                    ])
                )

            pos = block_stock_begin + 2800

        return result


"""
读取通达信备份的自定义板块文件夹，返回格式与通达信板块一致，在广发证券客户端上测试通过，其它未测试
"""


class CustomerBlockReader(BaseReader):

    def get_df(self, fname, result_type=BlockReader_TYPE_FLAT):
        result = self.get_data(fname, result_type)
        return pd.DataFrame(result)

    def get_data(self, fname, result_type=BlockReader_TYPE_FLAT):

        result = []

        if not os.path.isdir(fname):
            raise Exception('not a directory')

        block_file = '/'.join([fname,'blocknew.cfg'])

        if not os.path.exists(block_file):
            raise Exception('file not exists')

        block_data = open(block_file,'rb').read()

        pos = 0
        result = []
        # print(block_data.decode('gbk','ignore'))
        while pos < len(block_data):
            n1 = block_data[pos:pos + 50].decode('gbk', 'ignore').rstrip("\x00")
            n2 = block_data[pos + 50:pos + 120].decode('gbk', 'ignore').rstrip("\x00")
            pos = pos + 120
            
            n1 = n1.split('\x00')[0]
            n2 = n2.split('\x00')[0]
            bf = '/'.join([fname,n2 + '.blk'])
            if not os.path.exists(bf):
                raise Exception('file not exists')

            codes = open(bf).read().splitlines()
            if result_type == BlockReader_TYPE_FLAT:
                for index,code in enumerate(codes):
                    if code is not '':
                        result.append(
                            OrderedDict([
                                ("blockname",n1),
                                ("block_type",n2),
                                ('code_index',index),
                                ('code',code[1:])
                            ])
                        )

            if result_type == BlockReader_TYPE_GROUP:
                cc = [c[1:] for c in codes if c is not '']
                result.append(
                    OrderedDict([
                        ("blockname",n1),
                        ("block_type",n2),
                        ("stock_count",len(cc)),
                        ("code_list",",".join(cc))
                    ])
                )

        return result


if __name__ == '__main__':
    df = BlockReader().get_df("/Users/rainx/tmp/block_zs.dat")
    print(df)
    df2 = BlockReader().get_df("/Users/rainx/tmp/block_zs.dat", BlockReader_TYPE_GROUP)
    print(df2)
    df3 = CustomerBlockReader().get_df('C:/Users/fit/Desktop/blocknew')
    print(df3)
    df4 = CustomerBlockReader().get_df('C:/Users/fit/Desktop/blocknew',BlockReader_TYPE_GROUP)
    print(df4)
