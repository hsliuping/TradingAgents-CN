#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015-2023 Daniel Rodriguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Ssoftware Foundation, either version 3 of the License, or
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

from . import RSI


class RelativeMomentumIndex(RSI):
    '''
    Description:
    The Relative Momentum Index was developed by Roger Altman and was
    introduced in his article in the February, 1993 issue of Technical Analysis
    of Stocks & Commodities magazine.

    While your typical RSI counts up and down days from close to close, the
    Relative Momentum Index counts up and down days from the close relative to
    a close x number of days ago. The result is an RSI that is a bit smoother.

    Usage:
    Use in the same way you would any other RSI . There are overbought and
    oversold zones, and can also be used for divergence and trend analysis.

    See:
      - https://www.marketvolume.com/technicalanalysis/relativemomentumindex.asp
      - https://www.tradingview.com/script/UCm7fIvk-FREE-INDICATOR-Relative-Momentum-Index-RMI/
      - https://www.prorealcode.com/prorealtime-indicators/relative-momentum-index-rmi/

    '''
    alias = ('RMI', )

    linealias = (('rsi', 'rmi',),)  # add an alias for this class rmi -> rsi
    plotlines = dict(rsi=dict(_name='rmi'))  # change line plotting name

    params = (
        ('period', 20),
        ('lookback', 5),
    )

    def _plotlabel(self):
        # override to always print the lookback label and do it before movav
        plabels = [self.p.period]
        plabels += [self.p.lookback]
        plabels += [self.p.movav] * self.p.notdefault('movav')
        return plabels
