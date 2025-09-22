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

import uuid

from .. import Observer
from ..utils.py3 import with_metaclass

from ..trade import Trade


class Trades(Observer):
    '''This observer keeps track of full trades and plot the PnL level achieved
    when a trade is closed.

    A trade is open when a position goes from 0 (or crossing over 0) to X and
    is then closed when it goes back to 0 (or crosses over 0 in the opposite
    direction)

    Params:
      - ``pnlcomm`` (def: ``True``)

        Show net/profit and loss, i.e.: after commission. If set to ``False``
        if will show the result of trades before commission
    '''
    _stclock = True

    lines = ('pnlplus', 'pnlminus')

    params = dict(pnlcomm=True)

    plotinfo = dict(plot=True, subplot=True,
                    plotname='Trades - Net Profit/Loss',
                    plotymargin=0.10,
                    plothlines=[0.0])

    plotlines = dict(
        pnlplus=dict(_name='Positive',
                     ls='', marker='o', color='blue',
                     markersize=8.0, fillstyle='full'),
        pnlminus=dict(_name='Negative',
                      ls='', marker='o', color='red',
                      markersize=8.0, fillstyle='full')
    )

    def __init__(self):

        self.trades = 0

        self.trades_long = 0
        self.trades_short = 0

        self.trades_plus = 0
        self.trades_minus = 0

        self.trades_plus_gross = 0
        self.trades_minus_gross = 0

        self.trades_win = 0
        self.trades_win_max = 0
        self.trades_win_min = 0

        self.trades_loss = 0
        self.trades_loss_max = 0
        self.trades_loss_min = 0

        self.trades_length = 0
        self.trades_length_max = 0
        self.trades_length_min = 0

    def next(self):
        for trade in self._owner._tradespending:
            if trade.data not in self.ddatas:
                continue

            if not trade.isclosed:
                continue

            pnl = trade.pnlcomm if self.p.pnlcomm else trade.pnl

            if pnl >= 0.0:
                self.lines.pnlplus[0] = pnl
            else:
                self.lines.pnlminus[0] = pnl


class MetaDataTrades(Observer.__class__):
    def donew(cls, *args, **kwargs):
        _obj, args, kwargs = super(MetaDataTrades, cls).donew(*args, **kwargs)

        # Recreate the lines dynamically
        if _obj.params.usenames:
            lnames = tuple(x._name for x in _obj.datas)
        else:
            lnames = tuple('data{}'.format(x) for x in range(len(_obj.datas)))

        # Generate a new lines class
        linescls = cls.lines._derive(uuid.uuid4().hex, lnames, 0, ())

        # Instantiate lines
        _obj.lines = linescls()

        # Generate plotlines info
        markers = ['o', 'v', '^', '<', '>', '1', '2', '3', '4', '8', 's', 'p',
                   '*', 'h', 'H', '+', 'x', 'D', 'd']

        colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'b', 'g', 'r', 'c', 'm',
                  'y', 'k', 'b', 'g', 'r', 'c', 'm']

        basedict = dict(ls='', markersize=8.0, fillstyle='full')

        plines = dict()
        for lname, marker, color in zip(lnames, markers, colors):
            plines[lname] = d = basedict.copy()
            d.update(marker=marker, color=color)

        plotlines = cls.plotlines._derive(
            uuid.uuid4().hex, plines, [], recurse=True)
        _obj.plotlines = plotlines()

        return _obj, args, kwargs  # return the instantiated object and args


class DataTrades(with_metaclass(MetaDataTrades, Observer)):
    _stclock = True

    params = (('usenames', True),)

    plotinfo = dict(plot=True, subplot=True, plothlines=[0.0],
                    plotymargin=0.10)

    plotlines = dict()

    def next(self):
        for trade in self._owner._tradespending:
            if trade.data not in self.ddatas:
                continue

            if not trade.isclosed:
                continue

            self.lines[trade.data._id - 1][0] = trade.pnl
