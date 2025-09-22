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
'''

.. module:: linebuffer

Classes that hold the buffer for a *line* and can operate on it
with appends, forwarding, rewinding, resetting and other

.. moduleauthor:: Daniel Rodriguez

'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import array
import collections
import datetime
from itertools import islice
import math

from .utils.py3 import range, with_metaclass, string_types

from .lineroot import LineRoot, LineSingle, LineMultiple
from . import metabase
from .utils import num2date, time2num


NAN = float('NaN')


class LineBuffer(LineSingle):
    '''
    LineBuffer defines an interface to an "array.array" (or list) in which
    index 0 points to the item which is active for input and output.

    Positive indices fetch values from the past (left hand side)
    Negative indices fetch values from the future (if the array has been
    extended on the right hand side)

    With this behavior no index has to be passed around to entities which have
    to work with the current value produced by other entities: the value is
    always reachable at "0".

    Likewise storing the current value produced by "self" is done at 0.

    Additional operations to move the pointer (home, forward, extend, rewind,
    advance getzero) are provided

    The class can also hold "bindings" to other LineBuffers. When a value
    is set in this class
    it will also be set in the binding.
    '''

    UnBounded, QBuffer = (0, 1)

    def __init__(self):
        self.lines = [self]
        self.mode = self.UnBounded
        self.bindings = list()
        self.reset()
        self._tz = None

    def get_idx(self):
        return self._idx

    def set_idx(self, idx, force=False):
        # if QBuffer and the last position of the buffer was reached, keep
        # it (unless force) as index 0. This allows resampling
        #  - forward adds a position, but the 1st one is discarded, the 0 is
        #  invariant
        # force supports replaying, which needs the extra bar to float
        # forward/backwards, because the last input is read, and after a
        # "backwards" is used to update the previous data. Unless the position
        # 0 was moved to the previous index, it would fail
        if self.mode == self.QBuffer:
            if force or self._idx < self.lenmark:
                self._idx = idx
        else:  # default: UnBounded
            self._idx = idx

    idx = property(get_idx, set_idx)

    def reset(self):
        ''' Resets the internal buffer structure and the indices
        '''
        if self.mode == self.QBuffer:
            # add extrasize to ensure resample/replay work because they will
            # use backwards to erase the last bar/tick before delivering a new
            # bar The previous forward would have discarded the bar "period"
            # times ago and it will not come back. Having + 1 in the size
            # allows the forward without removing that bar
            self.array = collections.deque(maxlen=self.maxlen + self.extrasize)
            self.useislice = True
        else:
            self.array = array.array(str('d'))
            self.useislice = False

        self.lencount = 0
        self.idx = -1
        self.extension = 0

    def qbuffer(self, savemem=0, extrasize=0):
        self.mode = self.QBuffer
        self.maxlen = self._minperiod
        self.extrasize = extrasize
        self.lenmark = self.maxlen - (not self.extrasize)
        self.reset()

    def getindicators(self):
        return []

    def minbuffer(self, size):
        '''The linebuffer must guarantee the minimum requested size to be
        available.

        In non-dqbuffer mode, this is always true (of course until data is
        filled at the beginning, there are less values, but minperiod in the
        framework should account for this.

        In dqbuffer mode the buffer has to be adjusted for this if currently
        less than requested
        '''
        if self.mode != self.QBuffer or self.maxlen >= size:
            return

        self.maxlen = size
        self.lenmark = self.maxlen - (not self.extrasize)
        self.reset()

    def __len__(self):
        return self.lencount

    def buflen(self):
        ''' Real data that can be currently held in the internal buffer

        The internal buffer can be longer than the actual stored data to
        allow for "lookahead" operations. The real amount of data that is
        held/can be held in the buffer
        is returned
        '''
        return len(self.array) - self.extension

    def __getitem__(self, ago):
        return self.array[self.idx + ago]

    def get(self, ago=0, size=1):
        ''' Returns a slice of the array relative to *ago*

        Keyword Args:
            ago (int): Point of the array to which size will be added
            to return the slice size(int): size of the slice to return,
            can be positive or negative

        If size is positive *ago* will mark the end of the iterable and vice
        versa if size is negative

        Returns:
            A slice of the underlying buffer
        '''
        if self.useislice:
            start = self.idx + ago - size + 1
            end = self.idx + ago + 1
            return list(islice(self.array, start, end))

        return self.array[self.idx + ago - size + 1:self.idx + ago + 1]

    def getzeroval(self, idx=0):
        ''' Returns a single value of the array relative to the real zero
        of the buffer

        Keyword Args:
            idx (int): Where to start relative to the real start of the buffer
            size(int): size of the slice to return

        Returns:
            A slice of the underlying buffer
        '''
        return self.array[idx]

    def getzero(self, idx=0, size=1):
        ''' Returns a slice of the array relative to the real zero of the buffer

        Keyword Args:
            idx (int): Where to start relative to the real start of the buffer
            size(int): size of the slice to return

        Returns:
            A slice of the underlying buffer
        '''
        if self.useislice:
            return list(islice(self.array, idx, idx + size))

        return self.array[idx:idx + size]

    def __setitem__(self, ago, value):
        ''' Sets a value at position "ago" and executes any associated bindings

        Keyword Args:
            ago (int): Point of the array to which size will be added to return
            the slice
            value (variable): value to be set
        '''
        self.array[self.idx + ago] = value
        for binding in self.bindings:
            binding[ago] = value

    def set(self, value, ago=0):
        ''' Sets a value at position "ago" and executes any associated bindings

        Keyword Args:
            value (variable): value to be set
            ago (int): Point of the array to which size will be added to return
            the slice
        '''
        self.array[self.idx + ago] = value
        for binding in self.bindings:
            binding[ago] = value

    def home(self):
        ''' Rewinds the logical index to the beginning

        The underlying buffer remains untouched and the actual len can be found
        out with buflen
        '''
        self.idx = -1
        self.lencount = 0

    def forward(self, value=NAN, size=1):
        ''' Moves the logical index foward and enlarges the buffer as much as needed

        Keyword Args:
            value (variable): value to be set in new positins
            size (int): How many extra positions to enlarge the buffer
        '''
        self.idx += size
        self.lencount += size

        for i in range(size):
            self.array.append(value)

    def backwards(self, size=1, force=False):
        ''' Moves the logical index backwards and reduces the buffer as much as needed

        Keyword Args:
            size (int): How many extra positions to rewind and reduce the
            buffer
        '''
        # Go directly to property setter to support force
        self.set_idx(self._idx - size, force=force)
        self.lencount -= size
        for i in range(size):
            self.array.pop()

    def rewind(self, size=1):
        self.idx -= size
        self.lencount -= size

    def advance(self, size=1):
        ''' Advances the logical index without touching the underlying buffer

        Keyword Args:
            size (int): How many extra positions to move forward
        '''
        self.idx += size
        self.lencount += size

    def extend(self, value=NAN, size=0):
        ''' Extends the underlying array with positions that the index will not reach

        Keyword Args:
            value (variable): value to be set in new positins
            size (int): How many extra positions to enlarge the buffer

        The purpose is to allow for lookahead operations or to be able to
        set values in the buffer "future"
        '''
        self.extension += size
        for i in range(size):
            self.array.append(value)

    def addbinding(self, binding):
        ''' Adds another line binding

        Keyword Args:
            binding (LineBuffer): another line that must be set when this line
            becomes a value
        '''
        self.bindings.append(binding)
        # record in the binding when the period is starting (never sooner
        # than self)
        binding.updateminperiod(self._minperiod)

    def plot(self, idx=0, size=None):
        ''' Returns a slice of the array relative to the real zero of the buffer

        Keyword Args:
            idx (int): Where to start relative to the real start of the buffer
            size(int): size of the slice to return

        This is a variant of getzero which unless told otherwise returns the
        entire buffer, which is usually the idea behind plottint (all must
        plotted)

        Returns:
            A slice of the underlying buffer
        '''
        return self.getzero(idx, size or len(self))

    def plotrange(self, start, end):
        if self.useislice:
            return list(islice(self.array, start, end))

        return self.array[start:end]

    def oncebinding(self):
        '''
        Executes the bindings when running in "once" mode
        '''
        larray = self.array
        blen = self.buflen()
        for binding in self.bindings:
            binding.array[0:blen] = larray[0:blen]

    def bind2lines(self, binding=0):
        '''
        Stores a binding to another line. "binding" can be an index or a name
        '''
        if isinstance(binding, string_types):
            line = getattr(self._owner.lines, binding)
        else:
            line = self._owner.lines[binding]

        self.addbinding(line)

        return self

    bind2line = bind2lines

    def __call__(self, ago=None):
        '''Returns either a delayed verison of itself in the form of a
        LineDelay object or a timeframe adapting version with regards to a ago

        Param: ago (default: None)

          If ago is None or an instance of LineRoot (a lines object) the
          returned valued is a LineCoupler instance

          If ago is anything else, it is assumed to be an int and a LineDelay
          object will be returned
        '''
        from .lineiterator import LineCoupler
        if ago is None or isinstance(ago, LineRoot):
            return LineCoupler(self, ago)

        return LineDelay(self, ago)

    def _makeoperation(self, other, operation, r=False, _ownerskip=None):
        return LinesOperation(self, other, operation, r=r,
                              _ownerskip=_ownerskip)

    def _makeoperationown(self, operation, _ownerskip=None):
        return LineOwnOperation(self, operation, _ownerskip=_ownerskip)

    def _settz(self, tz):
        self._tz = tz

    def datetime(self, ago=0, tz=None, naive=True):
        return num2date(self.array[self.idx + ago],
                        tz=tz or self._tz, naive=naive)

    def date(self, ago=0, tz=None, naive=True):
        return num2date(self.array[self.idx + ago],
                        tz=tz or self._tz, naive=naive).date()

    def time(self, ago=0, tz=None, naive=True):
        return num2date(self.array[self.idx + ago],
                        tz=tz or self._tz, naive=naive).time()

    def dt(self, ago=0):
        '''
        return numeric date part of datetimefloat
        '''
        return math.trunc(self.array[self.idx + ago])

    def tm_raw(self, ago=0):
        '''
        return raw numeric time part of datetimefloat
        '''
        # This function is named raw because it retrieves the fractional part
        # without transforming it to time to avoid the influence of the day
        # count (integer part of coding)
        return math.modf(self.array[self.idx + ago])[0]

    def tm(self, ago=0):
        '''
        return numeric time part of datetimefloat
        '''
        # To avoid precision errors, this returns the fractional part after
        # having converted it to a datetime.time object to avoid precision
        # errors in comparisons
        return time2num(num2date(self.array[self.idx + ago]).time())

    def tm_lt(self, other, ago=0):
        '''
        return numeric time part of datetimefloat
        '''
        # To compare a raw "tm" part (fractional part of coded datetime)
        # with the tm of the current datetime, the raw "tm" has to be
        # brought in sync with the current "day" count (integer part) to avoid
        dtime = self.array[self.idx + ago]
        tm, dt = math.modf(dtime)

        return dtime < (dt + other)

    def tm_le(self, other, ago=0):
        '''
        return numeric time part of datetimefloat
        '''
        # To compare a raw "tm" part (fractional part of coded datetime)
        # with the tm of the current datetime, the raw "tm" has to be
        # brought in sync with the current "day" count (integer part) to avoid
        dtime = self.array[self.idx + ago]
        tm, dt = math.modf(dtime)

        return dtime <= (dt + other)

    def tm_eq(self, other, ago=0):
        '''
        return numeric time part of datetimefloat
        '''
        # To compare a raw "tm" part (fractional part of coded datetime)
        # with the tm of the current datetime, the raw "tm" has to be
        # brought in sync with the current "day" count (integer part) to avoid
        dtime = self.array[self.idx + ago]
        tm, dt = math.modf(dtime)

        return dtime == (dt + other)

    def tm_gt(self, other, ago=0):
        '''
        return numeric time part of datetimefloat
        '''
        # To compare a raw "tm" part (fractional part of coded datetime)
        # with the tm of the current datetime, the raw "tm" has to be
        # brought in sync with the current "day" count (integer part) to avoid
        dtime = self.array[self.idx + ago]
        tm, dt = math.modf(dtime)

        return dtime > (dt + other)

    def tm_ge(self, other, ago=0):
        '''
        return numeric time part of datetimefloat
        '''
        # To compare a raw "tm" part (fractional part of coded datetime)
        # with the tm of the current datetime, the raw "tm" has to be
        # brought in sync with the current "day" count (integer part) to avoid
        dtime = self.array[self.idx + ago]
        tm, dt = math.modf(dtime)

        return dtime >= (dt + other)

    def tm2dtime(self, tm, ago=0):
        '''
        Returns the given ``tm`` in the frame of the (ago bars) datatime.

        Useful for external comparisons to avoid precision errors
        '''
        return int(self.array[self.idx + ago]) + tm

    def tm2datetime(self, tm, ago=0):
        '''
        Returns the given ``tm`` in the frame of the (ago bars) datatime.

        Useful for external comparisons to avoid precision errors
        '''
        return num2date(int(self.array[self.idx + ago]) + tm)


class MetaLineActions(LineBuffer.__class__):
    '''
    Metaclass for Lineactions

    Scans the instance before init for LineBuffer (or parentclass LineSingle)
    instances to calculate the minperiod for this instance

    postinit it registers the instance to the owner (remember that owner has
    been found in the base Metaclass for LineRoot)
    '''
    _acache = dict()
    _acacheuse = False

    @classmethod
    def cleancache(cls):
        cls._acache = dict()

    @classmethod
    def usecache(cls, onoff):
        cls._acacheuse = onoff

    def __call__(cls, *args, **kwargs):
        if not cls._acacheuse:
            return super(MetaLineActions, cls).__call__(*args, **kwargs)

        # implement a cache to avoid duplicating lines actions
        ckey = (cls, tuple(args), tuple(kwargs.items()))  # tuples hashable
        try:
            return cls._acache[ckey]
        except TypeError:  # something not hashable
            return super(MetaLineActions, cls).__call__(*args, **kwargs)
        except KeyError:
            pass  # hashable but not in the cache

        _obj = super(MetaLineActions, cls).__call__(*args, **kwargs)
        return cls._acache.setdefault(ckey, _obj)

    def dopreinit(cls, _obj, *args, **kwargs):
        _obj, args, kwargs = \
            super(MetaLineActions, cls).dopreinit(_obj, *args, **kwargs)

        _obj._clock = _obj._owner  # default setting

        if isinstance(args[0], LineRoot):
            _obj._clock = args[0]

        # Keep a reference to the datas for buffer adjustment purposes
        _obj._datas = [x for x in args if isinstance(x, LineRoot)]

        # Do not produce anything until the operation lines produce something
        _minperiods = [x._minperiod for x in args if isinstance(x, LineSingle)]

        mlines = [x.lines[0] for x in args if isinstance(x, LineMultiple)]
        _minperiods += [x._minperiod for x in mlines]

        _minperiod = max(_minperiods or [1])

        # update own minperiod if needed
        _obj.updateminperiod(_minperiod)

        return _obj, args, kwargs

    def dopostinit(cls, _obj, *args, **kwargs):
        _obj, args, kwargs = \
            super(MetaLineActions, cls).dopostinit(_obj, *args, **kwargs)

        # register with _owner to be kicked later
        _obj._owner.addindicator(_obj)

        return _obj, args, kwargs


class PseudoArray(object):
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __getitem__(self, key):
        return self.wrapped

    @property
    def array(self):
        return self


class LineActions(with_metaclass(MetaLineActions, LineBuffer)):
    '''
    Base class derived from LineBuffer intented to defined the
    minimum interface to make it compatible with a LineIterator by
    providing operational _next and _once interfaces.

    The metaclass does the dirty job of calculating minperiods and registering
    '''

    _ltype = LineBuffer.IndType

    def getindicators(self):
        return []

    def qbuffer(self, savemem=0):
        super(LineActions, self).qbuffer(savemem=savemem)
        for data in self._datas:
            data.minbuffer(size=self._minperiod)

    @staticmethod
    def arrayize(obj):
        if isinstance(obj, LineRoot):
            if not isinstance(obj, LineSingle):
                obj = obj.lines[0]  # get 1st line from multiline
        else:
            obj = PseudoArray(obj)

        return obj

    def _next(self):
        clock_len = len(self._clock)
        if clock_len > len(self):
            self.forward()

        if clock_len > self._minperiod:
            self.next()
        elif clock_len == self._minperiod:
            # only called for the 1st value
            self.nextstart()
        else:
            self.prenext()

    def _once(self):
        self.forward(size=self._clock.buflen())
        self.home()

        self.preonce(0, self._minperiod - 1)
        self.oncestart(self._minperiod - 1, self._minperiod)
        self.once(self._minperiod, self.buflen())

        self.oncebinding()


def LineDelay(a, ago=0, **kwargs):
    if ago <= 0:
        return _LineDelay(a, ago, **kwargs)

    return _LineForward(a, ago, **kwargs)


def LineNum(num):
    return LineDelay(PseudoArray(num))


class _LineDelay(LineActions):
    '''
    Takes a LineBuffer (or derived) object and stores the value from
    "ago" periods effectively delaying the delivery of data
    '''
    def __init__(self, a, ago):
        super(_LineDelay, self).__init__()
        self.a = a
        self.ago = ago

        # Need to add the delay to the period. "ago" is 0 based and therefore
        # we need to pass and extra 1 which is the minimum defined period for
        # any data (which will be substracted inside addminperiod)
        self.addminperiod(abs(ago) + 1)

    def next(self):
        self[0] = self.a[self.ago]

    def once(self, start, end):
        # cache python dictionary lookups
        dst = self.array
        src = self.a.array
        ago = self.ago

        for i in range(start, end):
            dst[i] = src[i + ago]


class _LineForward(LineActions):
    '''
    Takes a LineBuffer (or derived) object and stores the value from
    "ago" periods from the future
    '''
    def __init__(self, a, ago):
        super(_LineForward, self).__init__()
        self.a = a
        self.ago = ago

        # Need to add the delay to the period. "ago" is 0 based and therefore
        # we need to pass and extra 1 which is the minimum defined period for
        # any data (which will be substracted inside addminperiod)
        # self.addminperiod(abs(ago) + 1)
        if ago > self.a._minperiod:
            self.addminperiod(ago - self.a._minperiod + 1)

    def next(self):
        self[-self.ago] = self.a[0]

    def once(self, start, end):
        # cache python dictionary lookups
        dst = self.array
        src = self.a.array
        ago = self.ago

        for i in range(start, end):
            dst[i - ago] = src[i]


class LinesOperation(LineActions):

    '''
    Holds an operation that operates on a two operands. Example: mul

    It will "next"/traverse the array applying the operation on the
    two operands and storing the result in self.

    To optimize the operations and avoid conditional checks the right
    next/once is chosen using the operation direction (normal or reversed)
    and the nature of the operands (LineBuffer vs non-LineBuffer)

    In the "once" operations "map" could be used as in:

        operated = map(self.operation, srca[start:end], srcb[start:end])
        self.array[start:end] = array.array(str(self.typecode), operated)

    No real execution time benefits were appreciated and therefore the loops
    have been kept in place for clarity (although the maps are not really
    unclear here)
    '''

    def __init__(self, a, b, operation, r=False):
        super(LinesOperation, self).__init__()

        self.operation = operation
        self.a = a  # always a linebuffer
        self.b = b

        self.r = r
        self.bline = isinstance(b, LineBuffer)
        self.btime = isinstance(b, datetime.time)
        self.bfloat = not self.bline and not self.btime

        if r:
            self.a, self.b = b, a

    def next(self):
        if self.bline:
            self[0] = self.operation(self.a[0], self.b[0])
        elif not self.r:
            if not self.btime:
                self[0] = self.operation(self.a[0], self.b)
            else:
                self[0] = self.operation(self.a.time(), self.b)
        else:
            self[0] = self.operation(self.a, self.b[0])

    def once(self, start, end):
        if self.bline:
            self._once_op(start, end)
        elif not self.r:
            if not self.btime:
                self._once_val_op(start, end)
            else:
                self._once_time_op(start, end)
        else:
            self._once_val_op_r(start, end)

    def _once_op(self, start, end):
        # cache python dictionary lookups
        dst = self.array
        srca = self.a.array
        srcb = self.b.array
        op = self.operation

        for i in range(start, end):
            dst[i] = op(srca[i], srcb[i])

    def _once_time_op(self, start, end):
        # cache python dictionary lookups
        dst = self.array
        srca = self.a.array
        srcb = self.b
        op = self.operation
        tz = self._tz

        for i in range(start, end):
            dst[i] = op(num2date(srca[i], tz=tz).time(), srcb)

    def _once_val_op(self, start, end):
        # cache python dictionary lookups
        dst = self.array
        srca = self.a.array
        srcb = self.b
        op = self.operation

        for i in range(start, end):
            dst[i] = op(srca[i], srcb)

    def _once_val_op_r(self, start, end):
        # cache python dictionary lookups
        dst = self.array
        srca = self.a
        srcb = self.b.array
        op = self.operation

        for i in range(start, end):
            dst[i] = op(srca, srcb[i])


class LineOwnOperation(LineActions):
    '''
    Holds an operation that operates on a single operand. Example: abs

    It will "next"/traverse the array applying the operation and storing
    the result in self
    '''
    def __init__(self, a, operation):
        super(LineOwnOperation, self).__init__()

        self.operation = operation
        self.a = a

    def next(self):
        self[0] = self.operation(self.a[0])

    def once(self, start, end):
        # cache python dictionary lookups
        dst = self.array
        srca = self.a.array
        op = self.operation

        for i in range(start, end):
            dst[i] = op(srca[i])
