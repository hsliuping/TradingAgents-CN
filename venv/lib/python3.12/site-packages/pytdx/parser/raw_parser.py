# coding=utf-8

from pytdx.parser.base import BaseParser

# Use this parser for testing


class RawParser(BaseParser):

    def setParams(self, pkg):
        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        return body_buf
