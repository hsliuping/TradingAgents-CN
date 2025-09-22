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

from . import Indicator, Max, MovAv
from . import DivZeroByZero


class UpDay(Indicator):
    '''
    Defined by J. Welles Wilder, Jr. in 1978 in his book *"New Concepts in
    Technical Trading Systems"* for the RSI

    Records days which have been "up", i.e.: the close price has been
    higher than the day before.

    Formula:
      - upday = max(close - close_prev, 0)

    See:
      - http://en.wikipedia.org/wiki/Relative_strength_index
    '''
    lines = ('upday',)
    params = (('period', 1),)

    def __init__(self):
        self.lines.upday = Max(self.data - self.data(-self.p.period), 0.0)
        super(UpDay, self).__init__()


class DownDay(Indicator):
    '''
    Defined by J. Welles Wilder, Jr. in 1978 in his book *"New Concepts in
    Technical Trading Systems"* for the RSI

    Records days which have been "down", i.e.: the close price has been
    lower than the day before.

    Formula:
      - downday = max(close_prev - close, 0)

    See:
      - http://en.wikipedia.org/wiki/Relative_strength_index
    '''
    lines = ('downday',)
    params = (('period', 1),)

    def __init__(self):
        self.lines.downday = Max(self.data(-self.p.period) - self.data, 0.0)
        super(DownDay, self).__init__()


class UpDayBool(Indicator):
    '''
    Defined by J. Welles Wilder, Jr. in 1978 in his book *"New Concepts in
    Technical Trading Systems"* for the RSI

    Records days which have been "up", i.e.: the close price has been
    higher than the day before.

    Note:
      - This version returns a bool rather than the difference

    Formula:
      - upday = close > close_prev

    See:
      - http://en.wikipedia.org/wiki/Relative_strength_index
    '''
    lines = ('upday',)
    params = (('period', 1),)

    def __init__(self):
        self.lines.upday = self.data > self.data(-self.p.period)
        super(UpDayBool, self).__init__()


class DownDayBool(Indicator):
    '''
    Defined by J. Welles Wilder, Jr. in 1978 in his book *"New Concepts in
    Technical Trading Systems"* for the RSI

    Records days which have been "down", i.e.: the close price has been
    lower than the day before.

    Note:
      - This version returns a bool rather than the difference

    Formula:
      - downday = close_prev > close

    See:
      - http://en.wikipedia.org/wiki/Relative_strength_index
    '''
    lines = ('downday',)
    params = (('period', 1),)

    def __init__(self):
        self.lines.downday = self.data(-self.p.period) > self.data
        super(DownDayBool, self).__init__()


class RelativeStrengthIndex(Indicator):
    '''Defined by J. Welles Wilder, Jr. in 1978 in his book *"New Concepts in
    Technical Trading Systems"*.

    It measures momentum by calculating the ration of higher closes and
    lower closes after having been smoothed by an average, normalizing
    the result between 0 and 100

    Formula:
      - up = upday(data)
      - down = downday(data)
      - maup = movingaverage(up, period)
      - madown = movingaverage(down, period)
      - rs = maup / madown
      - rsi = 100 - 100 / (1 + rs)

    The moving average used is the one originally defined by Wilder,
    the SmoothedMovingAverage

    See:
      - http://en.wikipedia.org/wiki/Relative_strength_index

    Notes:
      - ``safediv`` (default: False) If this parameter is True the division
        rs = maup / madown will be checked for the special cases in which a
        ``0 / 0`` or ``x / 0`` division will happen

      - ``safehigh`` (default: 100.0) will be used as RSI value for the
        ``x / 0`` case

      - ``safelow``  (default: 50.0) will be used as RSI value for the
        ``0 / 0`` case
    '''
    alias = ('RSI', 'RSI_SMMA', 'RSI_Wilder',)

    lines = ('rsi',)
    params = (
        ('period', 14),
        ('movav', MovAv.Smoothed),
        ('upperband', 70.0),
        ('lowerband', 30.0),
        ('safediv', False),
        ('safehigh', 100.0),
        ('safelow', 50.0),
        ('lookback', 1),
    )

    def _plotlabel(self):
        plabels = [self.p.period]
        plabels += [self.p.movav] * self.p.notdefault('movav')
        plabels += [self.p.lookback] * self.p.notdefault('lookback')
        return plabels

    def _plotinit(self):
        self.plotinfo.plotyhlines = [self.p.upperband, self.p.lowerband]

    def __init__(self):
        upday = UpDay(self.data, period=self.p.lookback)
        downday = DownDay(self.data, period=self.p.lookback)
        maup = self.p.movav(upday, period=self.p.period)
        madown = self.p.movav(downday, period=self.p.period)
        if not self.p.safediv:
            rs = maup / madown
        else:
            highrs = self._rscalc(self.p.safehigh)
            lowrs = self._rscalc(self.p.safelow)
            rs = DivZeroByZero(maup, madown, highrs, lowrs)

        self.lines.rsi = 100.0 - 100.0 / (1.0 + rs)
        super(RelativeStrengthIndex, self).__init__()

    def _rscalc(self, rsi):
        try:
            rs = (-100.0 / (rsi - 100.0)) - 1.0
        except ZeroDivisionError:
            return float('inf')

        return rs


class RSI_Safe(RSI):
    '''
    Subclass of RSI which changes parameers ``safediv`` to ``True`` as the
    default value

    See:
      - http://en.wikipedia.org/wiki/Relative_strength_index
    '''
    params = (('safediv', True),)


class RSI_SMA(RSI):
    '''
    Uses a SimpleMovingAverage as described in Wikipedia and other soures

    See:
      - http://en.wikipedia.org/wiki/Relative_strength_index
    '''
    alias = ('RSI_Cutler',)

    params = (('movav', MovAv.Simple),)


class RSI_EMA(RSI):
    '''
    Uses an ExponentialMovingAverage as described in Wikipedia

    See:
      - http://en.wikipedia.org/wiki/Relative_strength_index
    '''
    params = (('movav', MovAv.Exponential),)
