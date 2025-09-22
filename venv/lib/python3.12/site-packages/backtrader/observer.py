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


from .lineiterator import LineIterator, ObserverBase, StrategyBase
from backtrader.utils.py3 import with_metaclass


class MetaObserver(ObserverBase.__class__):
    def donew(cls, *args, **kwargs):
        _obj, args, kwargs = super(MetaObserver, cls).donew(*args, **kwargs)
        _obj._analyzers = list()  # keep children analyzers

        return _obj, args, kwargs  # return the instantiated object and args

    def dopreinit(cls, _obj, *args, **kwargs):
        _obj, args, kwargs = \
            super(MetaObserver, cls).dopreinit(_obj, *args, **kwargs)

        if _obj._stclock:  # Change clock if strategy wide observer
            _obj._clock = _obj._owner

        return _obj, args, kwargs


class Observer(with_metaclass(MetaObserver, ObserverBase)):
    _stclock = False

    _OwnerCls = StrategyBase
    _ltype = LineIterator.ObsType

    csv = True

    plotinfo = dict(plot=False, subplot=True)

    # An Observer is ideally always observing and that' why prenext calls
    # next. The behaviour can be overriden by subclasses
    def prenext(self):
        self.next()

    def _register_analyzer(self, analyzer):
        self._analyzers.append(analyzer)

    def _start(self):
        self.start()

    def start(self):
        pass
