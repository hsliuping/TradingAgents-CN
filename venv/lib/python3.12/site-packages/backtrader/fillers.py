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


from backtrader.utils.py3 import MAXINT, with_metaclass

from backtrader.metabase import MetaParams


class FixedSize(with_metaclass(MetaParams, object)):
    '''Returns the execution size for a given order using a *percentage* of the
    volume in a bar.

    This percentage is set with the parameter ``perc``

    Params:

      - ``size`` (default: ``None``)  maximum size to be executed. The actual
        volume of the bar at execution time is also a limit if smaller than the
        size

        If the value of this parameter evaluates to False, the entire volume
        of the bar will be used to match the order
    '''
    params = (('size', None),)

    def __call__(self, order, price, ago):
        size = self.p.size or MAXINT
        return min((order.data.volume[ago], abs(order.executed.remsize), size))


class FixedBarPerc(with_metaclass(MetaParams, object)):
    '''Returns the execution size for a given order using a *percentage* of the
    volume in a bar.

    This percentage is set with the parameter ``perc``

    Params:

      - ``perc`` (default: ``100.0``) (valied values: ``0.0 - 100.0``)

        Percentage of the volume bar to use to execute an order
    '''
    params = (('perc', 100.0),)

    def __call__(self, order, price, ago):
        # Get the volume and scale it to the requested perc
        maxsize = (order.data.volume[ago] * self.p.perc) // 100
        # Return the maximum possible executed volume
        return min(maxsize, abs(order.executed.remsize))


class BarPointPerc(with_metaclass(MetaParams, object)):
    '''Returns the execution size for a given order. The volume will be
    distributed uniformly in the range *high*-*low* using ``minmov`` to
    partition.

    From the allocated volume for the given price, the ``perc`` percentage will
    be used

    Params:

      - ``minmov`` (default: ``0.01``)

        Minimum price movement. Used to partition the range *high*-*low* to
        proportionally distribute the volume amongst possible prices

      - ``perc`` (default: ``100.0``) (valied values: ``0.0 - 100.0``)

        Percentage of the volume allocated to the order execution price to use
        for matching

    '''
    params = (
        ('minmov', None),
        ('perc', 100.0),
    )

    def __call__(self, order, price, ago):
        data = order.data
        minmov = self.p.minmov

        parts = 1
        if minmov:
            # high - low + minmov to account for open ended minus op
            parts = (data.high[ago] - data.low[ago] + minmov) // minmov

        alloc_vol = ((data.volume[ago] / parts) * self.p.perc) // 100.0

        # return max possible executable volume
        return min(alloc_vol, abs(order.executed.remsize))
