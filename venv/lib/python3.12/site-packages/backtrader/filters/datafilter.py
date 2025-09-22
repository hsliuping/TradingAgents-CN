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

import backtrader as bt


class DataFilter(bt.AbstractDataBase):
    '''
    This class filters out bars from a given data source. In addition to the
    standard parameters of a DataBase it takes a ``funcfilter`` parameter which
    can be any callable

    Logic:

      - ``funcfilter`` will be called with the underlying data source

        It can be any callable

        - Return value ``True``: current data source bar values will used
        - Return value ``False``: current data source bar values will discarded
    '''
    params = (('funcfilter', None),)

    def preload(self):
        if len(self.p.dataname) == self.p.dataname.buflen():
            # if data is not preloaded .... do it
            self.p.dataname.start()
            self.p.dataname.preload()
            self.p.dataname.home()

        # Copy timeframe from data after start (some sources do autodetection)
        self.p.timeframe = self._timeframe = self.p.dataname._timeframe
        self.p.compression = self._compression = self.p.dataname._compression

        super(DataFilter, self).preload()

    def _load(self):
        if not len(self.p.dataname):
            self.p.dataname.start()  # start data if not done somewhere else

        # Tell underlying source to get next data
        while self.p.dataname.next():
            # Try to load the data from the underlying source
            if not self.p.funcfilter(self.p.dataname):
                continue

            # Data is allowed - Copy size which is "number of lines"
            for i in range(self.p.dataname.size()):
                self.lines[i][0] = self.p.dataname.lines[i][0]

            return True

        return False  # no more data from underlying source
