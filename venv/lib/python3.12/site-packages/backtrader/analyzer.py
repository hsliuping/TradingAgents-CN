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

import calendar
from collections import OrderedDict
import datetime
import pprint as pp

import backtrader as bt
from backtrader import TimeFrame
from backtrader.utils.py3 import MAXINT, with_metaclass


class MetaAnalyzer(bt.MetaParams):
    def donew(cls, *args, **kwargs):
        '''
        Intercept the strategy parameter
        '''
        # Create the object and set the params in place
        _obj, args, kwargs = super(MetaAnalyzer, cls).donew(*args, **kwargs)

        _obj._children = list()

        _obj.strategy = strategy = bt.metabase.findowner(_obj, bt.Strategy)
        _obj._parent = bt.metabase.findowner(_obj, Analyzer)

        # Register with a master observer if created inside one
        masterobs = bt.metabase.findowner(_obj, bt.Observer)
        if masterobs is not None:
            masterobs._register_analyzer(_obj)

        _obj.datas = strategy.datas

        # For each data add aliases: for first data: data and data0
        if _obj.datas:
            _obj.data = data = _obj.datas[0]

            for l, line in enumerate(data.lines):
                linealias = data._getlinealias(l)
                if linealias:
                    setattr(_obj, 'data_%s' % linealias, line)
                setattr(_obj, 'data_%d' % l, line)

            for d, data in enumerate(_obj.datas):
                setattr(_obj, 'data%d' % d, data)

                for l, line in enumerate(data.lines):
                    linealias = data._getlinealias(l)
                    if linealias:
                        setattr(_obj, 'data%d_%s' % (d, linealias), line)
                    setattr(_obj, 'data%d_%d' % (d, l), line)

        _obj.create_analysis()

        # Return to the normal chain
        return _obj, args, kwargs

    def dopostinit(cls, _obj, *args, **kwargs):
        _obj, args, kwargs = \
            super(MetaAnalyzer, cls).dopostinit(_obj, *args, **kwargs)

        if _obj._parent is not None:
            _obj._parent._register(_obj)

        # Return to the normal chain
        return _obj, args, kwargs


class Analyzer(with_metaclass(MetaAnalyzer, object)):
    '''Analyzer base class. All analyzers are subclass of this one

    An Analyzer instance operates in the frame of a strategy and provides an
    analysis for that strategy.

    Automagically set member attributes:

      - ``self.strategy`` (giving access to the *strategy* and anything
        accessible from it)

      - ``self.datas[x]`` giving access to the array of data feeds present in
        the the system, which could also be accessed via the strategy reference

      - ``self.data``, giving access to ``self.datas[0]``

      - ``self.dataX`` -> ``self.datas[X]``

      - ``self.dataX_Y`` -> ``self.datas[X].lines[Y]``

      - ``self.dataX_name`` -> ``self.datas[X].name``

      - ``self.data_name`` -> ``self.datas[0].name``

      - ``self.data_Y`` -> ``self.datas[0].lines[Y]``

    This is not a *Lines* object, but the methods and operation follow the same
    design

      - ``__init__`` during instantiation and initial setup

      - ``start`` / ``stop`` to signal the begin and end of operations

      - ``prenext`` / ``nextstart`` / ``next`` family of methods that follow
        the calls made to the same methods in the strategy

      - ``notify_trade`` / ``notify_order`` / ``notify_cashvalue`` /
        ``notify_fund`` which receive the same notifications as the equivalent
        methods of the strategy

    The mode of operation is open and no pattern is preferred. As such the
    analysis can be generated with the ``next`` calls, at the end of operations
    during ``stop`` and even with a single method like ``notify_trade``

    The important thing is to override ``get_analysis`` to return a *dict-like*
    object containing the results of the analysis (the actual format is
    implementation dependent)

    '''
    csv = True

    def __len__(self):
        '''Support for invoking ``len`` on analyzers by actually returning the
        current length of the strategy the analyzer operates on'''
        return len(self.strategy)

    def _register(self, child):
        self._children.append(child)

    def _prenext(self):
        for child in self._children:
            child._prenext()

        self.prenext()

    def _notify_cashvalue(self, cash, value):
        for child in self._children:
            child._notify_cashvalue(cash, value)

        self.notify_cashvalue(cash, value)

    def _notify_fund(self, cash, value, fundvalue, shares):
        for child in self._children:
            child._notify_fund(cash, value, fundvalue, shares)

        self.notify_fund(cash, value, fundvalue, shares)

    def _notify_trade(self, trade):
        for child in self._children:
            child._notify_trade(trade)

        self.notify_trade(trade)

    def _notify_order(self, order):
        for child in self._children:
            child._notify_order(order)

        self.notify_order(order)

    def _nextstart(self):
        for child in self._children:
            child._nextstart()

        self.nextstart()

    def _next(self):
        for child in self._children:
            child._next()

        self.next()

    def _start(self):
        for child in self._children:
            child._start()

        self.start()

    def _stop(self):
        for child in self._children:
            child._stop()

        self.stop()

    def notify_cashvalue(self, cash, value):
        '''Receives the cash/value notification before each next cycle'''
        pass

    def notify_fund(self, cash, value, fundvalue, shares):
        '''Receives the current cash, value, fundvalue and fund shares'''
        pass

    def notify_order(self, order):
        '''Receives order notifications before each next cycle'''
        pass

    def notify_trade(self, trade):
        '''Receives trade notifications before each next cycle'''
        pass

    def next(self):
        '''Invoked for each next invocation of the strategy, once the minum
        preiod of the strategy has been reached'''
        pass

    def prenext(self):
        '''Invoked for each prenext invocation of the strategy, until the minimum
        period of the strategy has been reached

        The default behavior for an analyzer is to invoke ``next``
        '''
        self.next()

    def nextstart(self):
        '''Invoked exactly once for the nextstart invocation of the strategy,
        when the minimum period has been first reached
        '''
        self.next()

    def start(self):
        '''Invoked to indicate the start of operations, giving the analyzer
        time to setup up needed things'''
        pass

    def stop(self):
        '''Invoked to indicate the end of operations, giving the analyzer
        time to shut down needed things'''
        pass

    def create_analysis(self):
        '''Meant to be overriden by subclasses. Gives a chance to create the
        structures that hold the analysis.

        The default behaviour is to create a ``OrderedDict`` named ``rets``
        '''
        self.rets = OrderedDict()

    def get_analysis(self):
        '''Returns a *dict-like* object with the results of the analysis

        The keys and format of analysis results in the dictionary is
        implementation dependent.

        It is not even enforced that the result is a *dict-like object*, just
        the convention

        The default implementation returns the default OrderedDict ``rets``
        created by the default ``create_analysis`` method

        '''
        return self.rets

    def print(self, *args, **kwargs):
        '''Prints the results returned by ``get_analysis`` via a standard
        ``Writerfile`` object, which defaults to writing things to standard
        output
        '''
        writer = bt.WriterFile(*args, **kwargs)
        writer.start()
        pdct = dict()
        pdct[self.__class__.__name__] = self.get_analysis()
        writer.writedict(pdct)
        writer.stop()

    def pprint(self, *args, **kwargs):
        '''Prints the results returned by ``get_analysis`` using the pretty
        print Python module (*pprint*)
        '''
        pp.pprint(self.get_analysis(), *args, **kwargs)


class MetaTimeFrameAnalyzerBase(Analyzer.__class__):
    def __new__(meta, name, bases, dct):
        # Hack to support original method name
        if '_on_dt_over' in dct:
            dct['on_dt_over'] = dct.pop('_on_dt_over')  # rename method

        return super(MetaTimeFrameAnalyzerBase, meta).__new__(meta, name,
                                                              bases, dct)


class TimeFrameAnalyzerBase(with_metaclass(MetaTimeFrameAnalyzerBase,
                                           Analyzer)):
    params = (
        ('timeframe', None),
        ('compression', None),
        ('_doprenext', True),
    )

    def _start(self):
        # Override to add specific attributes
        self.timeframe = self.p.timeframe or self.data._timeframe
        self.compression = self.p.compression or self.data._compression

        self.dtcmp, self.dtkey = self._get_dt_cmpkey(datetime.datetime.min)
        super(TimeFrameAnalyzerBase, self)._start()

    def _prenext(self):
        for child in self._children:
            child._prenext()

        if self._dt_over():
            self.on_dt_over()

        if self.p._doprenext:
            self.prenext()

    def _nextstart(self):
        for child in self._children:
            child._nextstart()

        if self._dt_over() or not self.p._doprenext:  # exec if no prenext
            self.on_dt_over()

        self.nextstart()

    def _next(self):
        for child in self._children:
            child._next()

        if self._dt_over():
            self.on_dt_over()

        self.next()

    def on_dt_over(self):
        pass

    def _dt_over(self):
        if self.timeframe == TimeFrame.NoTimeFrame:
            dtcmp, dtkey = MAXINT, datetime.datetime.max
        else:
            # With >= 1.9.x the system datetime is in the strategy
            dt = self.strategy.datetime.datetime()
            dtcmp, dtkey = self._get_dt_cmpkey(dt)

        if self.dtcmp is None or dtcmp > self.dtcmp:
            self.dtkey, self.dtkey1 = dtkey, self.dtkey
            self.dtcmp, self.dtcmp1 = dtcmp, self.dtcmp
            return True

        return False

    def _get_dt_cmpkey(self, dt):
        if self.timeframe == TimeFrame.NoTimeFrame:
            return None, None

        if self.timeframe == TimeFrame.Years:
            dtcmp = dt.year
            dtkey = datetime.date(dt.year, 12, 31)

        elif self.timeframe == TimeFrame.Months:
            dtcmp = dt.year * 100 + dt.month
            _, lastday = calendar.monthrange(dt.year, dt.month)
            dtkey = datetime.datetime(dt.year, dt.month, lastday)

        elif self.timeframe == TimeFrame.Weeks:
            isoyear, isoweek, isoweekday = dt.isocalendar()
            dtcmp = isoyear * 100 + isoweek
            sunday = dt + datetime.timedelta(days=7 - isoweekday)
            dtkey = datetime.datetime(sunday.year, sunday.month, sunday.day)

        elif self.timeframe == TimeFrame.Days:
            dtcmp = dt.year * 10000 + dt.month * 100 + dt.day
            dtkey = datetime.datetime(dt.year, dt.month, dt.day)

        else:
            dtcmp, dtkey = self._get_subday_cmpkey(dt)

        return dtcmp, dtkey

    def _get_subday_cmpkey(self, dt):
        # Calculate intraday position
        point = dt.hour * 60 + dt.minute

        if self.timeframe < TimeFrame.Minutes:
            point = point * 60 + dt.second

        if self.timeframe < TimeFrame.Seconds:
            point = point * 1e6 + dt.microsecond

        # Apply compression to update point position (comp 5 -> 200 // 5)
        point = point // self.compression

        # Move to next boundary
        point += 1

        # Restore point to the timeframe units by de-applying compression
        point *= self.compression

        # Get hours, minutes, seconds and microseconds
        if self.timeframe == TimeFrame.Minutes:
            ph, pm = divmod(point, 60)
            ps = 0
            pus = 0
        elif self.timeframe == TimeFrame.Seconds:
            ph, pm = divmod(point, 60 * 60)
            pm, ps = divmod(pm, 60)
            pus = 0
        elif self.timeframe == TimeFrame.MicroSeconds:
            ph, pm = divmod(point, 60 * 60 * 1e6)
            pm, psec = divmod(pm, 60 * 1e6)
            ps, pus = divmod(psec, 1e6)

        extradays = 0
        if ph > 23:  # went over midnight:
            extradays = ph // 24
            ph %= 24

        # moving 1 minor unit to the left to be in the boundary
        # pm -= self.timeframe == TimeFrame.Minutes
        # ps -= self.timeframe == TimeFrame.Seconds
        # pus -= self.timeframe == TimeFrame.MicroSeconds

        tadjust = datetime.timedelta(
            minutes=self.timeframe == TimeFrame.Minutes,
            seconds=self.timeframe == TimeFrame.Seconds,
            microseconds=self.timeframe == TimeFrame.MicroSeconds)

        # Add extra day if present
        if extradays:
            dt += datetime.timedelta(days=extradays)

        # Replace intraday parts with the calculated ones and update it
        dtcmp = dt.replace(hour=ph, minute=pm, second=ps, microsecond=pus)
        dtcmp -= tadjust
        dtkey = dtcmp

        return dtcmp, dtkey
