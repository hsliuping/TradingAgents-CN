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

from . import Indicator, Max, Min, MovAv


class TrueHigh(Indicator):
    '''
    Defined by J. Welles Wilder, Jr. in 1978 in his book *"New Concepts in
    Technical Trading Systems"* for the ATR

    Records the "true high" which is the maximum of today's high and
    yesterday's close

    Formula:
      - truehigh = max(high, close_prev)

    See:
      - http://en.wikipedia.org/wiki/Average_true_range
    '''
    lines = ('truehigh',)

    def __init__(self):
        self.lines.truehigh = Max(self.data.high, self.data.close(-1))
        super(TrueHigh, self).__init__()


class TrueLow(Indicator):
    '''
    Defined by J. Welles Wilder, Jr. in 1978 in his book *"New Concepts in
    Technical Trading Systems"* for the ATR

    Records the "true low" which is the minimum of today's low and
    yesterday's close

    Formula:
      - truelow = min(low, close_prev)

    See:
      - http://en.wikipedia.org/wiki/Average_true_range
    '''
    lines = ('truelow',)

    def __init__(self):
        self.lines.truelow = Min(self.data.low, self.data.close(-1))
        super(TrueLow, self).__init__()


class TrueRange(Indicator):
    '''
    Defined by J. Welles Wilder, Jr. in 1978 in his book New Concepts in
    Technical Trading Systems.

    Formula:
      - max(high - low, abs(high - prev_close), abs(prev_close - low)

      which can be simplified to

      - max(high, prev_close) - min(low, prev_close)

    See:
      - http://en.wikipedia.org/wiki/Average_true_range

    The idea is to take the previous close into account to calculate the range
    if it yields a larger range than the daily range (High - Low)
    '''
    alias = ('TR',)

    lines = ('tr',)

    def __init__(self):
        self.lines.tr = TrueHigh(self.data) - TrueLow(self.data)
        super(TrueRange, self).__init__()


class AverageTrueRange(Indicator):
    '''
    Defined by J. Welles Wilder, Jr. in 1978 in his book *"New Concepts in
    Technical Trading Systems"*.

    The idea is to take the close into account to calculate the range if it
    yields a larger range than the daily range (High - Low)

    Formula:
      - SmoothedMovingAverage(TrueRange, period)

    See:
      - http://en.wikipedia.org/wiki/Average_true_range
    '''
    alias = ('ATR',)

    lines = ('atr',)
    params = (('period', 14), ('movav', MovAv.Smoothed))

    def _plotlabel(self):
        plabels = [self.p.period]
        plabels += [self.p.movav] * self.p.notdefault('movav')
        return plabels

    def __init__(self):
        self.lines.atr = self.p.movav(TR(self.data), period=self.p.period)
        super(AverageTrueRange, self).__init__()
