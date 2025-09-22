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

from .. import Observer


class Cash(Observer):
    '''This observer keeps track of the current amount of cash in the broker

    Params: None
    '''
    _stclock = True

    lines = ('cash',)

    plotinfo = dict(plot=True, subplot=True)

    def next(self):
        self.lines[0][0] = self._owner.broker.getcash()


class Value(Observer):
    '''This observer keeps track of the current portfolio value in the broker
    including the cash

    Params:

      - ``fund`` (default: ``None``)

        If ``None`` the actual mode of the broker (fundmode - True/False) will
        be autodetected to decide if the returns are based on the total net
        asset value or on the fund value. See ``set_fundmode`` in the broker
        documentation

        Set it to ``True`` or ``False`` for a specific behavior

    '''
    _stclock = True

    params = (
        ('fund', None),
    )

    lines = ('value',)

    plotinfo = dict(plot=True, subplot=True)

    def start(self):
        if self.p.fund is None:
            self._fundmode = self._owner.broker.fundmode
        else:
            self._fundmode = self.p.fund

    def next(self):
        if not self._fundmode:
            self.lines[0][0] = self._owner.broker.getvalue()
        else:
            self.lines[0][0] = self._owner.broker.fundvalue


class Broker(Observer):
    '''This observer keeps track of the current cash amount and portfolio value in
    the broker (including the cash)

    Params: None
    '''
    _stclock = True

    params = (
        ('fund', None),
    )

    alias = ('CashValue',)
    lines = ('cash', 'value')

    plotinfo = dict(plot=True, subplot=True)

    def start(self):
        if self.p.fund is None:
            self._fundmode = self._owner.broker.fundmode
        else:
            self._fundmode = self.p.fund

        if self._fundmode:
            self.plotlines.cash._plotskip = True
            self.plotlines.value._name = 'FundValue'

    def next(self):
        if not self._fundmode:
            self.lines.value[0] = value = self._owner.broker.getvalue()
            self.lines.cash[0] = self._owner.broker.getcash()
        else:
            self.lines.value[0] = self._owner.broker.fundvalue


class FundValue(Observer):
    '''This observer keeps track of the current fund-like value

    Params: None
    '''
    _stclock = True

    alias = ('FundShareValue', 'FundVal')
    lines = ('fundval',)

    plotinfo = dict(plot=True, subplot=True)

    def next(self):
        self.lines.fundval[0] = self._owner.broker.fundvalue


class FundShares(Observer):
    '''This observer keeps track of the current fund-like shares

    Params: None
    '''
    _stclock = True

    lines = ('fundshares',)

    plotinfo = dict(plot=True, subplot=True)

    def next(self):
        self.lines.fundshares[0] = self._owner.broker.fundshares
