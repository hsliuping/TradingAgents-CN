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

(

    SIGNAL_NONE,
    SIGNAL_LONGSHORT,
    SIGNAL_LONG,
    SIGNAL_LONG_INV,
    SIGNAL_LONG_ANY,
    SIGNAL_SHORT,
    SIGNAL_SHORT_INV,
    SIGNAL_SHORT_ANY,
    SIGNAL_LONGEXIT,
    SIGNAL_LONGEXIT_INV,
    SIGNAL_LONGEXIT_ANY,
    SIGNAL_SHORTEXIT,
    SIGNAL_SHORTEXIT_INV,
    SIGNAL_SHORTEXIT_ANY,

) = range(14)


SignalTypes = [
    SIGNAL_NONE,
    SIGNAL_LONGSHORT,
    SIGNAL_LONG, SIGNAL_LONG_INV, SIGNAL_LONG_ANY,
    SIGNAL_SHORT, SIGNAL_SHORT_INV, SIGNAL_SHORT_ANY,
    SIGNAL_LONGEXIT, SIGNAL_LONGEXIT_INV, SIGNAL_LONGEXIT_ANY,
    SIGNAL_SHORTEXIT, SIGNAL_SHORTEXIT_INV, SIGNAL_SHORTEXIT_ANY
]


class Signal(bt.Indicator):
    SignalTypes = SignalTypes

    lines = ('signal',)

    def __init__(self):
        self.lines.signal = self.data0.lines[0]
        self.plotinfo.plotmaster = getattr(self.data0, '_clock', self.data0)
