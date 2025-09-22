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

from datetime import datetime
from struct import unpack
import os.path

import backtrader as bt
from backtrader import date2num  # avoid dict lookups


class MetaVChartFile(bt.DataBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaVChartFile, cls).__init__(name, bases, dct)

        # Register with the store
        bt.stores.VChartFile.DataCls = cls


class VChartFile(bt.with_metaclass(MetaVChartFile, bt.DataBase)):
    '''
    Support for `Visual Chart <www.visualchart.com>`_ binary on-disk files for
    both daily and intradaily formats.

    Note:

      - ``dataname``: Market code displayed by Visual Chart. Example: 015ES for
        EuroStoxx 50 continuous future
    '''

    def start(self):
        super(VChartFile, self).start()
        if self._store is None:
            self._store = bt.stores.VChartFile()
            self._store.start()

        self._store.start(data=self)

        # Choose extension and extraction/calculation parameters
        if self.p.timeframe < bt.TimeFrame.Minutes:
            ext = '.tck'  # seconds will still need resampling
            # FIXME: find reference to tick counter for format
        elif self.p.timeframe < bt.TimeFrame.Days:
            ext = '.min'
            self._dtsize = 2
            self._barsize = 32
            self._barfmt = 'IIffffII'
        else:
            ext = '.fd'
            self._barsize = 28
            self._dtsize = 1
            self._barfmt = 'IffffII'

        # Construct full path
        basepath = self._store.get_datapath()

        # Example: 01 + 0 + 015ES + .fd -> 010015ES.fd
        dataname = '01' + '0' + self.p.dataname + ext
        # 015ES -> 0 + 015 -> 0015
        mktcode = '0' + self.p.dataname[0:3]

        # basepath/0015/010015ES.fd
        path = os.path.join(basepath, mktcode, dataname)
        try:
            self.f = open(path, 'rb')
        except IOError:
            self.f = None

    def stop(self):
        if self.f is not None:
            self.f.close()
            self.f = None

    def _load(self):
        if self.f is None:
            return False  # cannot load more

        try:
            bardata = self.f.read(self._barsize)
        except IOError:
            self.f = None  # cannot return, nullify file
            return False  # cannot load more

        if not bardata or len(bardata) < self._barsize:
            self.f = None  # cannot return, nullify file
            return False  # cannot load more

        try:
            bdata = unpack(self._barfmt, bardata)
        except:
            self.f = None
            return False

        # First Date
        y, md = divmod(bdata[0], 500)  # Years stored as if they had 500 days
        m, d = divmod(md, 32)  # Months stored as if they had 32 days
        dt = datetime(y, m, d)

        # Time
        if self._dtsize > 1:  # Minute Bars
            # Daily Time is stored in seconds
            hhmm, ss = divmod(bdata[1], 60)
            hh, mm = divmod(hhmm, 60)
            dt = dt.replace(hour=hh, minute=mm, second=ss)
        else:  # Daily Bars
            dt = datetime.combine(dt, self.p.sessionend)

        self.lines.datetime[0] = date2num(dt)  # Store time

        # Get the rest of the fields
        o, h, l, c, v, oi = bdata[self._dtsize:]
        self.lines.open[0] = o
        self.lines.high[0] = h
        self.lines.low[0] = l
        self.lines.close[0] = c
        self.lines.volume[0] = v
        self.lines.openinterest[0] = oi

        return True  # a bar has been successfully loaded
