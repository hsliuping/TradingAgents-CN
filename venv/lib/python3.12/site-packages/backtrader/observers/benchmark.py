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
from . import TimeReturn


class Benchmark(TimeReturn):
    '''This observer stores the *returns* of the strategy and the *return* of a
    reference asset which is one of the datas passed to the system.

    Params:

      - ``timeframe`` (default: ``None``)
        If ``None`` then the complete return over the entire backtested period
        will be reported

      - ``compression`` (default: ``None``)

        Only used for sub-day timeframes to for example work on an hourly
        timeframe by specifying "TimeFrame.Minutes" and 60 as compression

      - ``data`` (default: ``None``)

        Reference asset to track to allow for comparison.

        .. note:: this data must have been added to a ``cerebro`` instance with
                  ``addata``, ``resampledata`` or ``replaydata``.


      - ``_doprenext`` (default: ``False``)

        Benchmarking will take place from the point at which the strategy kicks
        in (i.e.: when the minimum period of the strategy has been met).

        Setting this to ``True`` will record benchmarking values from the
        starting point of the data feeds

      - ``firstopen`` (default: ``False``)

        Keepint it as ``False`` ensures that the 1st comparison point between
        the value and the benchmark starts at 0%, because the benchmark will
        not use its opening price.

        See the ``TimeReturn`` analyzer reference for a full explanation of the
        meaning of the parameter

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

    lines = ('benchmark',)
    plotlines = dict(benchmark=dict(_name='Benchmark'))

    params = (
        ('data', None),
        ('_doprenext', False),
        # Set to false to ensure the asset is measured at 0% in the 1st tick
        ('firstopen', False),
        ('fund', None)
    )

    def _plotlabel(self):
        labels = super(Benchmark, self)._plotlabel()
        labels.append(self.p.data._name)
        return labels

    def __init__(self):
        if self.p.data is None:  # use the 1st data in the system if none given
            self.p.data = self.data0

        super(Benchmark, self).__init__()  # treturn including data parameter
        # Create a time return object without the data
        kwargs = self.p._getkwargs()
        kwargs.update(data=None)  # to create a return for the stratey
        t = self._owner._addanalyzer_slave(bt.analyzers.TimeReturn, **kwargs)

        # swap for consistency
        self.treturn, self.tbench = t, self.treturn

    def next(self):
        super(Benchmark, self).next()
        self.lines.benchmark[0] = self.tbench.rets.get(self.treturn.dtkey,
                                                       float('NaN'))

    def prenext(self):
        if self.p._doprenext:
            super(TimeReturn, self).prenext()
