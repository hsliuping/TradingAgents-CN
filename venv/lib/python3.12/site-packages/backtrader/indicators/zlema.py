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


from . import Indicator, MovingAverageBase, MovAv


class ZeroLagExponentialMovingAverage(MovingAverageBase):
    '''
    The zero-lag exponential moving average (ZLEMA) is a variation of the EMA
    which adds a momentum term aiming to reduce lag in the average so as to
    track current prices more closely.

    Formula:
      - lag = (period - 1) / 2
      - zlema = ema(2 * data - data(-lag))

    See also:
      - http://user42.tuxfamily.org/chart/manual/Zero_002dLag-Exponential-Moving-Average.html

    '''
    alias = ('ZLEMA', 'ZeroLagEma',)
    lines = ('zlema',)
    params = (('_movav', MovAv.EMA),)

    def __init__(self):
        lag = (self.p.period - 1) // 2
        data = 2 * self.data - self.data(-lag)
        self.lines.zlema = self.p._movav(data, period=self.p.period)

        super(ZeroLagExponentialMovingAverage, self).__init__()
