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
# Python 2/3 compatibility imports
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from . import Indicator, MovAv


class DetrendedPriceOscillator(Indicator):
    '''
    Defined by Joe DiNapoli in his book *"Trading with DiNapoli levels"*

    It measures the price variations against a Moving Average (the trend)
    and therefore removes the "trend" factor from the price.

    Formula:
      - movav = MovingAverage(close, period)
      - dpo = close - movav(shifted period / 2 + 1)

    See:
      - http://en.wikipedia.org/wiki/Detrended_price_oscillator
    '''
    # Named alias for invocation
    alias = ('DPO',)

    # Named output lines
    lines = ('dpo',)

    # Accepted parameters (and defaults) -
    # MovAvg also parameter to allow experimentation
    params = (('period', 20), ('movav', MovAv.Simple))

    # Emphasize central 0.0 line in plot
    plotinfo = dict(plothlines=[0.0])

    # Indicator information after the name (in brackets)
    def _plotlabel(self):
        plabels = [self.p.period]
        plabels += [self.p.movav] * self.p.notdefault('movav')
        return plabels

    def __init__(self):
        # Create the Moving Average
        ma = self.p.movav(self.data, period=self.p.period)

        # Calculate value (look back period/2 + 1 in MA) and bind to 'dpo' line
        self.lines.dpo = self.data - ma(-self.p.period // 2 + 1)

        super(DetrendedPriceOscillator, self).__init__()
