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

from . import Indicator, MovAv, StdDev


class BollingerBands(Indicator):
    '''
    Defined by John Bollinger in the 80s. It measures volatility by defining
    upper and lower bands at distance x standard deviations

    Formula:
      - midband = SimpleMovingAverage(close, period)
      - topband = midband + devfactor * StandardDeviation(data, period)
      - botband = midband - devfactor * StandardDeviation(data, period)

    See:
      - http://en.wikipedia.org/wiki/Bollinger_Bands
    '''
    alias = ('BBands',)

    lines = ('mid', 'top', 'bot',)
    params = (('period', 20), ('devfactor', 2.0), ('movav', MovAv.Simple),)

    plotinfo = dict(subplot=False)
    plotlines = dict(
        mid=dict(ls='--'),
        top=dict(_samecolor=True),
        bot=dict(_samecolor=True),
    )

    def _plotlabel(self):
        plabels = [self.p.period, self.p.devfactor]
        plabels += [self.p.movav] * self.p.notdefault('movav')
        return plabels

    def __init__(self):
        self.lines.mid = ma = self.p.movav(self.data, period=self.p.period)
        stddev = self.p.devfactor * StdDev(self.data, ma, period=self.p.period,
                                           movav=self.p.movav)
        self.lines.top = ma + stddev
        self.lines.bot = ma - stddev

        super(BollingerBands, self).__init__()


class BollingerBandsPct(BollingerBands):
    '''
    Extends the Bollinger Bands with a Percentage line
    '''
    lines = ('pctb',)
    plotlines = dict(pctb=dict(_name='%B'))  # display the line as %B on chart

    def __init__(self):
        super(BollingerBandsPct, self).__init__()
        self.l.pctb = (self.data - self.l.bot) / (self.l.top - self.l.bot)
