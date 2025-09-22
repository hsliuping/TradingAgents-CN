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
from backtrader.indicators import SumN, TrueLow, TrueRange


class UltimateOscillator(bt.Indicator):
    '''
    Formula:
      # Buying Pressure = Close - TrueLow
      BP = Close - Minimum(Low or Prior Close)

      # TrueRange = TrueHigh - TrueLow
      TR = Maximum(High or Prior Close)  -  Minimum(Low or Prior Close)

      Average7 = (7-period BP Sum) / (7-period TR Sum)
      Average14 = (14-period BP Sum) / (14-period TR Sum)
      Average28 = (28-period BP Sum) / (28-period TR Sum)

      UO = 100 x [(4 x Average7)+(2 x Average14)+Average28]/(4+2+1)

    See:

      - https://en.wikipedia.org/wiki/Ultimate_oscillator
      - http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:ultimate_oscillator
    '''
    lines = ('uo',)

    params = (
        ('p1', 7),
        ('p2', 14),
        ('p3', 28),
        ('upperband', 70.0),
        ('lowerband', 30.0),
    )

    def _plotinit(self):
        baseticks = [10.0, 50.0, 90.0]
        hlines = [self.p.upperband, self.p.lowerband]

        # Plot lines at 0 & 100 to make the scale complete + upper/lower/bands
        self.plotinfo.plotyhlines = hlines
        # Plot ticks at "baseticks" + the user specified upper/lower bands
        self.plotinfo.plotyticks = baseticks + hlines

    def __init__(self):
        bp = self.data.close - TrueLow(self.data)
        tr = TrueRange(self.data)

        av7 = SumN(bp, period=self.p.p1) / SumN(tr, period=self.p.p1)
        av14 = SumN(bp, period=self.p.p2) / SumN(tr, period=self.p.p2)
        av28 = SumN(bp, period=self.p.p3) / SumN(tr, period=self.p.p3)

        # Multiply/divide floats outside of formula to reduce line objects
        factor = 100.0 / (4.0 + 2.0 + 1.0)
        uo = (4.0 * factor) * av7 + (2.0 * factor) * av14 + factor * av28
        self.lines.uo = uo

        super(UltimateOscillator, self).__init__()
