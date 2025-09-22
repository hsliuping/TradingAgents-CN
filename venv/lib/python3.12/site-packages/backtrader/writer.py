#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015-2023 Daniel Rodriguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import collections
import io
import itertools
import sys

try:  # For new Python versions
    collectionsAbc = collections.abc  # collections.Iterable -> collections.abc.Iterable
except AttributeError:  # For old Python versions
    collectionsAbc = collections  # Используем collections.Iterable

import backtrader as bt
from backtrader.utils.py3 import (map, with_metaclass, string_types,
                                  integer_types)


class WriterBase(with_metaclass(bt.MetaParams, object)):
    pass


class WriterFile(WriterBase):
    '''The system wide writer class.

    It can be parametrized with:

      - ``out`` (default: ``sys.stdout``): output stream to write to

        If a string is passed a filename with the content of the parameter will
        be used.

        If you wish to run with ``sys.stdout`` while doing multiprocess optimization, leave it as ``None``, which will
        automatically initiate ``sys.stdout`` on the child processes.

      - ``close_out``  (default: ``False``)

        If ``out`` is a stream whether it has to be explicitly closed by the
        writer

      - ``csv`` (default: ``False``)

        If a csv stream of the data feeds, strategies, observers and indicators
        has to be written to the stream during execution

        Which objects actually go into the csv stream can be controlled with
        the ``csv`` attribute of each object (defaults to ``True`` for ``data
        feeds`` and ``observers`` / False for ``indicators``)

      - ``csv_filternan`` (default: ``True``) whether ``nan`` values have to be
        purged out of the csv stream (replaced by an empty field)

      - ``csv_counter`` (default: ``True``) if the writer shall keep and print
        out a counter of the lines actually output

      - ``indent`` (default: ``2``) indentation spaces for each level

      - ``separators`` (default: ``['=', '-', '+', '*', '.', '~', '"', '^',
        '#']``)

        Characters used for line separators across section/sub(sub)sections

      - ``seplen`` (default: ``79``)

        total length of a line separator including indentation

      - ``rounding`` (default: ``None``)

        Number of decimal places to round floats down to. With ``None`` no
        rounding is performed

    '''
    params = (
        ('out', None),
        ('close_out', False),

        ('csv', False),
        ('csvsep', ','),
        ('csv_filternan', True),
        ('csv_counter', True),

        ('indent', 2),
        ('separators', ['=', '-', '+', '*', '.', '~', '"', '^', '#']),
        ('seplen', 79),
        ('rounding', None),
    )

    def __init__(self):
        self._len = itertools.count(1)
        self.headers = list()
        self.values = list()

    def _start_output(self):
        # open file if needed
        if not hasattr(self, 'out') or not self.out:
            if self.p.out is None:
                self.out = sys.stdout
                self.close_out = False
            elif isinstance(self.p.out, string_types):
                self.out = open(self.p.out, 'w')
                self.close_out = True
            else:
                self.out = self.p.out
                self.close_out = self.p.close_out

    def start(self):
        self._start_output()

        if self.p.csv:
            self.writelineseparator()
            self.writeiterable(self.headers, counter='Id')

    def stop(self):
        if self.close_out:
            self.out.close()

    def next(self):
        if self.p.csv:
            self.writeiterable(self.values, func=str, counter=next(self._len))
            self.values = list()

    def addheaders(self, headers):
        if self.p.csv:
            self.headers.extend(headers)

    def addvalues(self, values):
        if self.p.csv:
            if self.p.csv_filternan:
                values = map(lambda x: x if x == x else '', values)
            self.values.extend(values)

    def writeiterable(self, iterable, func=None, counter=''):
        if self.p.csv_counter:
            iterable = itertools.chain([counter], iterable)

        if func is not None:
            iterable = map(lambda x: func(x), iterable)

        line = self.p.csvsep.join(iterable)
        self.writeline(line)

    def writeline(self, line):
        self.out.write(line + '\n')

    def writelines(self, lines):
        for l in lines:
            self.out.write(l + '\n')

    def writelineseparator(self, level=0):
        sepnum = level % len(self.p.separators)
        separator = self.p.separators[sepnum]

        line = ' ' * (level * self.p.indent)
        line += separator * (self.p.seplen - (level * self.p.indent))
        self.writeline(line)

    def writedict(self, dct, level=0, recurse=False):
        if not recurse:
            self.writelineseparator(level)

        indent0 = level * self.p.indent
        for key, val in dct.items():
            kline = ' ' * indent0
            if recurse:
                kline += '- '

            kline += str(key) + ':'

            try:
                sclass = issubclass(val, bt.LineSeries)
            except TypeError:
                sclass = False

            if sclass:
                kline += ' ' + val.__name__
                self.writeline(kline)
            elif isinstance(val, string_types):
                kline += ' ' + val
                self.writeline(kline)
            elif isinstance(val, integer_types):
                kline += ' ' + str(val)
                self.writeline(kline)
            elif isinstance(val, float):
                if self.p.rounding is not None:
                    val = round(val, self.p.rounding)
                kline += ' ' + str(val)
                self.writeline(kline)
            elif isinstance(val, dict):
                if recurse:
                    self.writelineseparator(level=level)
                self.writeline(kline)
                self.writedict(val, level=level + 1, recurse=True)
            elif isinstance(val, (list, tuple, collectionsAbc.Iterable)):  # Для разных версий Python будут вызываться разные функции
                line = ', '.join(map(str, val))
                self.writeline(kline + ' ' + line)
            else:
                kline += ' ' + str(val)
                self.writeline(kline)


class WriterStringIO(WriterFile):
    params = (('out', io.StringIO),)

    def __init__(self):
        super(WriterStringIO, self).__init__()

    def _start_output(self):
        super(WriterStringIO, self)._start_output()
        self.out = self.out()

    def stop(self):
        super(WriterStringIO, self).stop()
        # Leave the file positioned at the beginning
        self.out.seek(0)
