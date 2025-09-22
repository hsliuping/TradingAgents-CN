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

from . import PeriodN


__all__ = ['LaguerreRSI', 'LRSI', 'LaguerreFilter', 'LAGF']


class LaguerreRSI(PeriodN):
    '''
    Defined by John F. Ehlers in `Cybernetic Analysis for Stock and Futures`,
    2004, published by Wiley. `ISBN: 978-0-471-46307-8`

    The Laguerre RSI tries to implements a better RSI by providing a sort of
    *Time Warp without Time Travel* using a Laguerre filter. This provides for
    faster reactions to price changes

    ``gamma`` is meant to have values between ``0.2`` and ``0.8``, with the
    best balance found theoretically at the default of ``0.5``
    '''
    alias = ('LRSI',)
    lines = ('lrsi',)
    params = (
        ('gamma', 0.5),
        ('period', 6),
    )

    plotinfo = dict(
        plotymargin=0.15,
        plotyticks=[0.0, 0.2, 0.5, 0.8, 1.0]
    )

    l0, l1, l2, l3 = 0.0, 0.0, 0.0, 0.0

    def next(self):
        l0_1 = self.l0  # cache previous intermediate values
        l1_1 = self.l1
        l2_1 = self.l2

        g = self.p.gamma  # avoid more lookups
        self.l0 = l0 = (1.0 - g) * self.data + g * l0_1
        self.l1 = l1 = -g * l0 + l0_1 + g * l1_1
        self.l2 = l2 = -g * l1 + l1_1 + g * l2_1
        self.l3 = l3 = -g * l2 + l2_1 + g * self.l3

        cu = 0.0
        cd = 0.0
        if l0 >= l1:
            cu = l0 - l1
        else:
            cd = l1 - l0

        if l1 >= l2:
            cu += l1 - l2
        else:
            cd += l2 - l1

        if l2 >= l3:
            cu += l2 - l3
        else:
            cd += l3 - l2

        den = cu + cd
        self.lines.lrsi[0] = 1.0 if not den else cu / den


class LaguerreFilter(PeriodN):
    '''
    Defined by John F. Ehlers in `Cybernetic Analysis for Stock and Futures`,
    2004, published by Wiley. `ISBN: 978-0-471-46307-8`

    ``gamma`` is meant to have values between ``0.2`` and ``0.8``, with the
    best balance found theoretically at the default of ``0.5``
    '''
    alias = ('LAGF',)
    lines = ('lfilter',)
    params = (('gamma', 0.5),)
    plotinfo = dict(subplot=False)

    l0, l1, l2, l3 = 0.0, 0.0, 0.0, 0.0

    def next(self):
        l0_1 = self.l0  # cache previous intermediate values
        l1_1 = self.l1
        l2_1 = self.l2

        g = self.p.gamma  # avoid more lookups
        self.l0 = l0 = (1.0 - g) * self.data + g * l0_1
        self.l1 = l1 = -g * l0 + l0_1 + g * l1_1
        self.l2 = l2 = -g * l1 + l1_1 + g * l2_1
        self.l3 = l3 = -g * l2 + l2_1 + g * self.l3
        self.lines.lfilter[0] = (l0 + (2 * l1) + (2 * l2) + l3) / 6
