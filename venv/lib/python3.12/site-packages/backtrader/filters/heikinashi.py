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


__all__ = ['HeikinAshi']


class HeikinAshi(object):
    '''
    The filter remodels the open, high, low, close to make HeikinAshi
    candlesticks

    See:
      - https://en.wikipedia.org/wiki/Candlestick_chart#Heikin_Ashi_candlesticks
      - http://stockcharts.com/school/doku.php?id=chart_school:chart_analysis:heikin_ashi

    '''
    def __init__(self, data):
        pass

    def __call__(self, data):
        o, h, l, c = data.open[0], data.high[0], data.low[0], data.close[0]

        data.close[0] = ha_close0 = (o + h + l + c) / 4.0

        if len(data) > 1:
            data.open[0] = ha_open0 = (data.open[-1] + data.close[-1]) / 2.0
            data.high[0] = max(ha_open0, ha_close0, h)
            data.low[0] = min(ha_open0, ha_close0, l)

        else:  # len is 1, no lookback is possible
            data.open[0] = ha_open0 = (o + c) / 2.0

        return False  # length of data stream is unaltered
