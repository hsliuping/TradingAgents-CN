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
from backtrader.utils.py3 import range


__all__ = ['HeikinAshi']


class HeikinAshi(bt.Indicator):
    '''
    Heikin Ashi candlesticks in the forms of lines

    Formula:
        ha_open = (ha_open(-1) + ha_close(-1)) / 2
        ha_high = max(hi, ha_open, ha_close)
        ha_low = min(lo, ha_open, ha_close)
        ha_close = (open + high + low + close) / 4

    See also:
        https://en.wikipedia.org/wiki/Candlestick_chart#Heikin_Ashi_candlesticks
        http://stockcharts.com/school/doku.php?id=chart_school:chart_analysis:heikin_ashi
    '''
    lines = ('ha_open', 'ha_high', 'ha_low', 'ha_close',)

    linealias = (
        ('ha_open', 'open',),
        ('ha_high', 'high',),
        ('ha_low', 'low',),
        ('ha_close', 'close',),
    )

    plotinfo = dict(subplot=False)

    _nextforce = True

    def __init__(self):
        o = self.data.open
        h = self.data.high
        l = self.data.low
        c = self.data.close

        self.l.ha_close = ha_close = (o + h + l + c) / 4.0
        self.l.ha_open = ha_open = (self.l.ha_open(-1) + ha_close(-1)) / 2.0
        self.l.ha_high = bt.Max(h, ha_open, ha_close)
        self.l.ha_low = bt.Min(l, ha_open, ha_close)

        super(HeikinAshi, self).__init__()

    def prenext(self):
        # seed recursive value
        self.lines.ha_open[0] = (self.data.open[0] + self.data.close[0]) / 2.0
