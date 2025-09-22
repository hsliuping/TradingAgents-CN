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


from .utils.py3 import range, with_metaclass

from .lineiterator import LineIterator, IndicatorBase
from .lineseries import LineSeriesMaker, Lines
from .metabase import AutoInfoClass


class MetaIndicator(IndicatorBase.__class__):
    _refname = '_indcol'
    _indcol = dict()

    _icache = dict()
    _icacheuse = False

    @classmethod
    def cleancache(cls):
        cls._icache = dict()

    @classmethod
    def usecache(cls, onoff):
        cls._icacheuse = onoff

    # Object cache deactivated on 2016-08-17. If the object is being used
    # inside another object, the minperiod information carried over
    # influences the first usage when being modified during the 2nd usage

    def __call__(cls, *args, **kwargs):
        if not cls._icacheuse:
            return super(MetaIndicator, cls).__call__(*args, **kwargs)

        # implement a cache to avoid duplicating lines actions
        ckey = (cls, tuple(args), tuple(kwargs.items()))  # tuples hashable
        try:
            return cls._icache[ckey]
        except TypeError:  # something not hashable
            return super(MetaIndicator, cls).__call__(*args, **kwargs)
        except KeyError:
            pass  # hashable but not in the cache

        _obj = super(MetaIndicator, cls).__call__(*args, **kwargs)
        return cls._icache.setdefault(ckey, _obj)

    def __init__(cls, name, bases, dct):
        '''
        Class has already been created ... register subclasses
        '''
        # Initialize the class
        super(MetaIndicator, cls).__init__(name, bases, dct)

        if not cls.aliased and \
           name != 'Indicator' and not name.startswith('_'):
            refattr = getattr(cls, cls._refname)
            refattr[name] = cls

        # Check if next and once have both been overridden
        next_over = cls.next != IndicatorBase.next
        once_over = cls.once != IndicatorBase.once

        if next_over and not once_over:
            # No -> need pointer movement to once simulation via next
            cls.once = cls.once_via_next
            cls.preonce = cls.preonce_via_prenext
            cls.oncestart = cls.oncestart_via_nextstart


class Indicator(with_metaclass(MetaIndicator, IndicatorBase)):
    _ltype = LineIterator.IndType

    csv = False

    def advance(self, size=1):
        # Need intercepting this call to support datas with
        # different lengths (timeframes)
        if len(self) < len(self._clock):
            self.lines.advance(size=size)

    def preonce_via_prenext(self, start, end):
        # generic implementation if prenext is overridden but preonce is not
        for i in range(start, end):
            for data in self.datas:
                data.advance()

            for indicator in self._lineiterators[LineIterator.IndType]:
                indicator.advance()

            self.advance()
            self.prenext()

    def oncestart_via_nextstart(self, start, end):
        # nextstart has been overriden, but oncestart has not and the code is
        # here. call the overriden nextstart
        for i in range(start, end):
            for data in self.datas:
                data.advance()

            for indicator in self._lineiterators[LineIterator.IndType]:
                indicator.advance()

            self.advance()
            self.nextstart()

    def once_via_next(self, start, end):
        # Not overridden, next must be there ...
        for i in range(start, end):
            for data in self.datas:
                data.advance()

            for indicator in self._lineiterators[LineIterator.IndType]:
                indicator.advance()

            self.advance()
            self.next()


class MtLinePlotterIndicator(Indicator.__class__):
    def donew(cls, *args, **kwargs):
        lname = kwargs.pop('name')
        name = cls.__name__

        lines = getattr(cls, 'lines', Lines)
        cls.lines = lines._derive(name, (lname,), 0, [])

        plotlines = AutoInfoClass
        newplotlines = dict()
        newplotlines.setdefault(lname, dict())
        cls.plotlines = plotlines._derive(name, newplotlines, [], recurse=True)

        # Create the object and set the params in place
        _obj, args, kwargs =  \
            super(MtLinePlotterIndicator, cls).donew(*args, **kwargs)

        _obj.owner = _obj.data.owner._clock
        _obj.data.lines[0].addbinding(_obj.lines[0])

        # Return the object and arguments to the chain
        return _obj, args, kwargs


class LinePlotterIndicator(with_metaclass(MtLinePlotterIndicator, Indicator)):
    pass
