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


__all__ = ['LogReturns', 'LogReturns2']


class LogReturns(bt.Observer):
    '''This observer stores the *log returns* of the strategy or a

    Params:

      - ``timeframe`` (default: ``None``)
        If ``None`` then the complete return over the entire backtested period
        will be reported

        Pass ``TimeFrame.NoTimeFrame`` to consider the entire dataset with no
        time constraints

      - ``compression`` (default: ``None``)

        Only used for sub-day timeframes to for example work on an hourly
        timeframe by specifying "TimeFrame.Minutes" and 60 as compression

      - ``fund`` (default: ``None``)

        If ``None`` the actual mode of the broker (fundmode - True/False) will
        be autodetected to decide if the returns are based on the total net
        asset value or on the fund value. See ``set_fundmode`` in the broker
        documentation

        Set it to ``True`` or ``False`` for a specific behavior

    Remember that at any moment of a ``run`` the current values can be checked
    by looking at the *lines* by name at index ``0``.

    '''
    _stclock = True

    lines = ('logret1',)
    plotinfo = dict(plot=True, subplot=True)

    params = (
        ('timeframe', None),
        ('compression', None),
        ('fund', None),
    )

    def _plotlabel(self):
        return [bt.TimeFrame.getname(self.p.timeframe, self.p.compression),
                str(self.p.compression or 1)]

    def __init__(self):
        self.logret1 = self._owner._addanalyzer_slave(
            bt.analyzers.LogReturnsRolling,
            data=self.data0, **self.p._getkwargs())

    def next(self):
        self.lines.logret1[0] = self.logret1.rets[self.logret1.dtkey]


class LogReturns2(LogReturns):
    '''Extends the observer LogReturns to show two instruments'''
    lines = ('logret2',)

    def __init__(self):
        super(LogReturns2, self).__init__()

        self.logret2 = self._owner._addanalyzer_slave(
            bt.analyzers.LogReturnsRolling,
            data=self.data1, **self.p._getkwargs())

    def next(self):
        super(LogReturns2, self).next()
        self.lines.logret2[0] = self.logret2.rets[self.logret2.dtkey]
