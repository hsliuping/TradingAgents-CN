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

from . import Indicator, And


class NonZeroDifference(Indicator):
    '''
    Keeps track of the difference between two data inputs skipping, memorizing
    the last non zero value if the current difference is zero

    Formula:
      - diff = data - data1
      - nzd = diff if diff else diff(-1)
    '''
    _mindatas = 2  # requires two (2) data sources
    alias = ('NZD',)
    lines = ('nzd',)

    def nextstart(self):
        self.l.nzd[0] = self.data0[0] - self.data1[0]  # seed value

    def next(self):
        d = self.data0[0] - self.data1[0]
        self.l.nzd[0] = d if d else self.l.nzd[-1]

    def oncestart(self, start, end):
        self.line.array[start] = (
            self.data0.array[start] - self.data1.array[start])

    def once(self, start, end):
        d0array = self.data0.array
        d1array = self.data1.array
        larray = self.line.array

        prev = larray[start - 1]
        for i in range(start, end):
            d = d0array[i] - d1array[i]
            larray[i] = prev = d if d else prev


class _CrossBase(Indicator):
    _mindatas = 2

    lines = ('cross',)

    plotinfo = dict(plotymargin=0.05, plotyhlines=[0.0, 1.0])

    def __init__(self):
        nzd = NonZeroDifference(self.data0, self.data1)

        if self._crossup:
            before = nzd(-1) < 0.0  # data0 was below or at 0
            after = self.data0 > self.data1
        else:
            before = nzd(-1) > 0.0  # data0 was above or at 0
            after = self.data0 < self.data1

        self.lines.cross = And(before, after)


class CrossUp(_CrossBase):
    '''
    This indicator gives a signal if the 1st provided data crosses over the 2nd
    indicator upwards

    It does need to look into the current time index (0) and the previous time
    index (-1) of both the 1st and 2nd data

    Formula:
      - diff = data - data1
      - upcross =  last_non_zero_diff < 0 and data0(0) > data1(0)
    '''
    _crossup = True


class CrossDown(_CrossBase):
    '''
    This indicator gives a signal if the 1st provided data crosses over the 2nd
    indicator upwards

    It does need to look into the current time index (0) and the previous time
    index (-1) of both the 1st and 2nd data

    Formula:
      - diff = data - data1
      - downcross = last_non_zero_diff > 0 and data0(0) < data1(0)
    '''
    _crossup = False


class CrossOver(Indicator):
    '''
    This indicator gives a signal if the provided datas (2) cross up or down.

      - 1.0 if the 1st data crosses the 2nd data upwards
      - -1.0 if the 1st data crosses the 2nd data downwards

    It does need to look into the current time index (0) and the previous time
    index (-1) of both the 1t and 2nd data

    Formula:
      - diff = data - data1
      - upcross =  last_non_zero_diff < 0 and data0(0) > data1(0)
      - downcross = last_non_zero_diff > 0 and data0(0) < data1(0)
      - crossover = upcross - downcross
    '''
    _mindatas = 2

    lines = ('crossover',)

    plotinfo = dict(plotymargin=0.05, plotyhlines=[-1.0, 1.0])

    def __init__(self):
        upcross = CrossUp(self.data, self.data1)
        downcross = CrossDown(self.data, self.data1)

        self.lines.crossover = upcross - downcross
