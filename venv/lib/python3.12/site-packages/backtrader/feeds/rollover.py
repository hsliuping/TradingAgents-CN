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


from datetime import datetime

import backtrader as bt


class MetaRollOver(bt.DataBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaRollOver, cls).__init__(name, bases, dct)

    def donew(cls, *args, **kwargs):
        '''Intercept const. to copy timeframe/compression from 1st data'''
        # Create the object and set the params in place
        _obj, args, kwargs = super(MetaRollOver, cls).donew(*args, **kwargs)

        if args:
            _obj.p.timeframe = args[0]._timeframe
            _obj.p.compression = args[0]._compression

        return _obj, args, kwargs


class RollOver(bt.with_metaclass(MetaRollOver, bt.DataBase)):
    '''Class that rolls over to the next future when a condition is met

    Params:

        - ``checkdate`` (default: ``None``)

          This must be a *callable* with the following signature::

            checkdate(dt, d):

          Where:

            - ``dt`` is a ``datetime.datetime`` object
            - ``d`` is the current data feed for the active future

          Expected Return Values:

            - ``True``: as long as the callable returns this, a switchover can
              happen to the next future

        If a commodity expires on the 3rd Friday of March, ``checkdate`` could
        return ``True`` for the entire week in which the expiration takes
        place.

            - ``False``: the expiration cannot take place

        - ``checkcondition`` (default: ``None``)

          **Note**: This will only be called if ``checkdate`` has returned
          ``True``

          If ``None`` this will evaluate to ``True`` (execute roll over)
          internally

          Else this must be a *callable* with this signature::

            checkcondition(d0, d1)

          Where:

            - ``d0`` is the current data feed for the active future
            - ``d1`` is the data feed for the next expiration

          Expected Return Values:

            - ``True``: roll-over to the next future

        Following with the example from ``checkdate``, this could say that the
        roll-over can only happend if the *volume* from ``d0`` is already less
        than the volume from ``d1``

            - ``False``: the expiration cannot take place
    '''

    params = (
        # ('rolls', []),  # array of futures to roll over
        ('checkdate', None),  # callable
        ('checkcondition', None),  # callable
    )

    def islive(self):
        '''Returns ``True`` to notify ``Cerebro`` that preloading and runonce
        should be deactivated'''
        return True

    def __init__(self, *args):
        self._rolls = args

    def start(self):
        super(RollOver, self).start()
        for d in self._rolls:
            d.setenvironment(self._env)
            d._start()

        # put the references in a separate list to have pops
        self._ds = list(self._rolls)
        self._d = self._ds.pop(0) if self._ds else None
        self._dexp = None
        self._dts = [datetime.min for xx in self._ds]

    def stop(self):
        super(RollOver, self).stop()
        for d in self._rolls:
            d.stop()

    def _gettz(self):
        '''To be overriden by subclasses which may auto-calculate the
        timezone'''
        if self._rolls:
            return self._rolls[0]._gettz()
        return bt.utils.date.Localizer(self.p.tz)

    def _checkdate(self, dt, d):
        if self.p.checkdate is not None:
            return self.p.checkdate(dt, d)

        return False

    def _checkcondition(self, d0, d1):
        if self.p.checkcondition is not None:
            return self.p.checkcondition(d0, d1)

        return True

    def _load(self):
        while self._d is not None:
            _next = self._d.next()
            if _next is None:  # no values yet, more will come
                continue
            if _next is False:  # no values from current data src
                if self._ds:
                    self._d = self._ds.pop(0)
                    self._dts.pop(0)
                else:
                    self._d = None
                continue

            dt0 = self._d.datetime.datetime()  # current dt for active data

            # Synchronize other datas using dt0
            for i, d_dt in enumerate(zip(self._ds, self._dts)):
                d, dt = d_dt
                while dt < dt0:
                    if d.next() is None:
                        continue
                    self._dts[i] = dt = d.datetime.datetime()

            # Move expired future as much as needed
            while self._dexp is not None:
                if not self._dexp.next():
                    self._dexp = None
                    break

                if self._dexp.datetime.datetime() < dt0:
                    continue

            if self._dexp is None and self._checkdate(dt0, self._d):
                # rule has been met ... check other factors only if 2 datas
                # still there
                if self._ds and self._checkcondition(self._d, self._ds[0]):
                    # Time to switch to next data
                    self._dexp = self._d
                    self._d = self._ds.pop(0)
                    self._dts.pop(0)

            # Fill the line and tell we die
            self.lines.datetime[0] = self._d.lines.datetime[0]
            self.lines.open[0] = self._d.lines.open[0]
            self.lines.high[0] = self._d.lines.high[0]
            self.lines.low[0] = self._d.lines.low[0]
            self.lines.close[0] = self._d.lines.close[0]
            self.lines.volume[0] = self._d.lines.volume[0]
            self.lines.openinterest[0] = self._d.lines.openinterest[0]
            return True

        # Out of the loop -> self._d is None, no data feed to return from
        return False
