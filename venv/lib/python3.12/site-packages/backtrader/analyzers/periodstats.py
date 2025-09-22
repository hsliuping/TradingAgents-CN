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
from backtrader.utils.py3 import itervalues
from backtrader.mathsupport import average, standarddev
from . import TimeReturn


__all__ = ['PeriodStats']


class PeriodStats(bt.Analyzer):
    '''Calculates basic statistics for given timeframe

    Params:

      - ``timeframe`` (default: ``Years``)
        If ``None`` the ``timeframe`` of the 1st data in the system will be
        used

        Pass ``TimeFrame.NoTimeFrame`` to consider the entire dataset with no
        time constraints

      - ``compression`` (default: ``1``)

        Only used for sub-day timeframes to for example work on an hourly
        timeframe by specifying "TimeFrame.Minutes" and 60 as compression

        If ``None`` then the compression of the 1st data of the system will be
        used

      - ``fund`` (default: ``None``)

        If ``None`` the actual mode of the broker (fundmode - True/False) will
        be autodetected to decide if the returns are based on the total net
        asset value or on the fund value. See ``set_fundmode`` in the broker
        documentation

        Set it to ``True`` or ``False`` for a specific behavior


    ``get_analysis`` returns a dictionary containing the keys:

      - ``average``
      - ``stddev``
      - ``positive``
      - ``negative``
      - ``nochange``
      - ``best``
      - ``worst``

    If the parameter ``zeroispos`` is set to ``True``, periods with no change
    will be counted as positive
    '''

    params = (
        ('timeframe', bt.TimeFrame.Years),
        ('compression', 1),
        ('zeroispos', False),
        ('fund', None),
    )

    def __init__(self):
        self._tr = TimeReturn(timeframe=self.p.timeframe,
                              compression=self.p.compression, fund=self.p.fund)

    def stop(self):
        trets = self._tr.get_analysis()  # dict key = date, value = ret
        pos = nul = neg = 0
        trets = list(itervalues(trets))
        for tret in trets:
            if tret > 0.0:
                pos += 1
            elif tret < 0.0:
                neg += 1
            else:
                if self.p.zeroispos:
                    pos += tret == 0.0
                else:
                    nul += tret == 0.0

        self.rets['average'] = avg = average(trets)
        self.rets['stddev'] = standarddev(trets, avg)

        self.rets['positive'] = pos
        self.rets['negative'] = neg
        self.rets['nochange'] = nul

        self.rets['best'] = max(trets)
        self.rets['worst'] = min(trets)
