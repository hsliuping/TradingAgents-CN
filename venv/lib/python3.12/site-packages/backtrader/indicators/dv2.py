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


from . import Indicator, SMA, PercentRank


__all__ = ['DV2']


class DV2(Indicator):
    '''
    RSI(2) alternative
    Developed by David Varadi of http://cssanalytics.wordpress.com/

    This seems to be the *Bounded* version.

    See also:

      - http://web.archive.org/web/20131216100741/http://quantingdutchman.wordpress.com/2010/08/06/dv2-indicator-for-amibroker/

    '''
    params = (
        ('period', 252),
        ('maperiod', 2),
        ('_movav', SMA),
    )
    lines = ('dv2',)

    def __init__(self):
        chl = self.data.close / ((self.data.high + self.data.low) / 2.0)
        dvu = self.p._movav(chl, period=self.p.maperiod)
        self.lines.dv2 = PercentRank(dvu, period=self.p.period) * 100
        super(DV2, self).__init__()
