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

from . import Indicator, FindFirstIndexHighest, FindFirstIndexLowest


class _AroonBase(Indicator):
    '''
    Base class which does the calculation of the AroonUp/AroonDown values and
    defines the common parameters.

    It uses the class attributes _up and _down (boolean flags) to decide which
    value has to be calculated.

    Values are not assigned to lines but rather stored in the "up" and "down"
    instance variables, which can be used by subclasses to for assignment or
    further calculations
    '''
    _up = False
    _down = False

    params = (('period', 14), ('upperband', 70), ('lowerband', 30),)
    plotinfo = dict(plotymargin=0.05, plotyhlines=[0, 100])

    def _plotlabel(self):
        plabels = [self.p.period]
        return plabels

    def _plotinit(self):
        self.plotinfo.plotyhlines += [self.p.lowerband, self.p.upperband]

    def __init__(self):
        # Look backwards period + 1 for current data because the formula mus
        # produce values between 0 and 100 and can only do that if the
        # calculated hhidx/llidx go from 0 to period (hence period + 1 values)
        idxperiod = self.p.period + 1

        if self._up:
            hhidx = FindFirstIndexHighest(self.data.high, period=idxperiod)
            self.up = (100.0 / self.p.period) * (self.p.period - hhidx)

        if self._down:
            llidx = FindFirstIndexLowest(self.data.low, period=idxperiod)
            self.down = (100.0 / self.p.period) * (self.p.period - llidx)

        super(_AroonBase, self).__init__()


class AroonUp(_AroonBase):
    '''
    This is the AroonUp from the indicator AroonUpDown developed by Tushar
    Chande in 1995.

    Formula:
      - up = 100 * (period - distance to highest high) / period

    Note:
      The lines oscillate between 0 and 100. That means that the "distance" to
      the last highest or lowest must go from 0 to period so that the formula
      can yield 0 and 100.

      Hence the lookback period is period + 1, because the current bar is also
      taken into account. And therefore this indicator needs an effective
      lookback period of period + 1.

    See:
      - http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:aroon
    '''
    _up = True

    lines = ('aroonup',)

    def __init__(self):
        super(AroonUp, self).__init__()

        self.lines.aroonup = self.up


class AroonDown(_AroonBase):
    '''
    This is the AroonDown from the indicator AroonUpDown developed by Tushar
    Chande in 1995.

    Formula:
      - down = 100 * (period - distance to lowest low) / period

    Note:
      The lines oscillate between 0 and 100. That means that the "distance" to
      the last highest or lowest must go from 0 to period so that the formula
      can yield 0 and 100.

      Hence the lookback period is period + 1, because the current bar is also
      taken into account. And therefore this indicator needs an effective
      lookback period of period + 1.

    See:
      - http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:aroon
    '''
    _down = True

    lines = ('aroondown',)

    def __init__(self):
        super(AroonDown, self).__init__()

        self.lines.aroondown = self.down


class AroonUpDown(AroonUp, AroonDown):
    '''
    Developed by Tushar Chande in 1995.

    It tries to determine if a trend exists or not by calculating how far away
    within a given period the last highs/lows are (AroonUp/AroonDown)

    Formula:
      - up = 100 * (period - distance to highest high) / period
      - down = 100 * (period - distance to lowest low) / period

    Note:
      The lines oscillate between 0 and 100. That means that the "distance" to
      the last highest or lowest must go from 0 to period so that the formula
      can yield 0 and 100.

      Hence the lookback period is period + 1, because the current bar is also
      taken into account. And therefore this indicator needs an effective
      lookback period of period + 1.

    See:
      - http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:aroon
    '''
    alias = ('AroonIndicator',)


class AroonOscillator(_AroonBase):
    '''
    It is a variation of the AroonUpDown indicator which shows the current
    difference between the AroonUp and AroonDown value, trying to present a
    visualization which indicates which is stronger (greater than 0 -> AroonUp
    and less than 0 -> AroonDown)

    Formula:
      - aroonosc = aroonup - aroondown

    See:
      - http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:aroon
    '''
    _up = True
    _down = True

    alias = ('AroonOsc',)

    lines = ('aroonosc',)

    def _plotinit(self):
        super(AroonOscillator, self)._plotinit()

        for yhline in self.plotinfo.plotyhlines[:]:
            self.plotinfo.plotyhlines.append(-yhline)

    def __init__(self):
        super(AroonOscillator, self).__init__()

        self.lines.aroonosc = self.up - self.down


class AroonUpDownOscillator(AroonUpDown, AroonOscillator):
    '''
    Presents together the indicators AroonUpDown and AroonOsc

    Formula:
      (None, uses the aforementioned indicators)

    See:
      - http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:aroon
    '''
    alias = ('AroonUpDownOsc',)
