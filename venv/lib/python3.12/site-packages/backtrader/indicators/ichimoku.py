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
from . import Highest, Lowest


class Ichimoku(bt.Indicator):
    '''
    Developed and published in his book in 1969 by journalist Goichi Hosoda

    Formula:
      - tenkan_sen = (Highest(High, tenkan) + Lowest(Low, tenkan)) / 2.0
      - kijun_sen = (Highest(High, kijun) + Lowest(Low, kijun)) / 2.0

      The next 2 are pushed 26 bars into the future

      - senkou_span_a = (tenkan_sen + kijun_sen) / 2.0
      - senkou_span_b = ((Highest(High, senkou) + Lowest(Low, senkou)) / 2.0

      This is pushed 26 bars into the past

      - chikou = close

    The cloud (Kumo) is formed by the area between the senkou_spans

    See:
      - http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:ichimoku_cloud

    '''
    lines = ('tenkan_sen', 'kijun_sen',
             'senkou_span_a', 'senkou_span_b', 'chikou_span',)
    params = (
        ('tenkan', 9),
        ('kijun', 26),
        ('senkou', 52),
        ('senkou_lead', 26),  # forward push
        ('chikou', 26),  # backwards push
    )

    plotinfo = dict(subplot=False)
    plotlines = dict(
        senkou_span_a=dict(_fill_gt=('senkou_span_b', 'g'),
                           _fill_lt=('senkou_span_b', 'r')),
    )

    def __init__(self):
        hi_tenkan = Highest(self.data.high, period=self.p.tenkan)
        lo_tenkan = Lowest(self.data.low, period=self.p.tenkan)
        self.l.tenkan_sen = (hi_tenkan + lo_tenkan) / 2.0

        hi_kijun = Highest(self.data.high, period=self.p.kijun)
        lo_kijun = Lowest(self.data.low, period=self.p.kijun)
        self.l.kijun_sen = (hi_kijun + lo_kijun) / 2.0

        senkou_span_a = (self.l.tenkan_sen + self.l.kijun_sen) / 2.0
        self.l.senkou_span_a = senkou_span_a(-self.p.senkou_lead)

        hi_senkou = Highest(self.data.high, period=self.p.senkou)
        lo_senkou = Lowest(self.data.low, period=self.p.senkou)
        senkou_span_b = (hi_senkou + lo_senkou) / 2.0
        self.l.senkou_span_b = senkou_span_b(-self.p.senkou_lead)

        self.l.chikou_span = self.data.close(self.p.chikou)

        super(Ichimoku, self).__init__()
