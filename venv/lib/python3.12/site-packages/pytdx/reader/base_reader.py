#coding=utf-8
from __future__ import unicode_literals, division
import struct


class TdxFileNotFoundException(Exception):
    pass

class TdxNotAssignVipdocPathException(Exception):
    pass


class BaseReader(object):

    def unpack_records(self, format, data):
        record_struct = struct.Struct(format)
        return (record_struct.unpack_from(data, offset)
                for offset in range(0, len(data), record_struct.size))

    def get_df(self, code_or_file, exchange=None):
        raise NotImplementedError('not yet')