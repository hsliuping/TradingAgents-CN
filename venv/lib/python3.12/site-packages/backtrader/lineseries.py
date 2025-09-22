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

.. module:: lineroot

Defines LineSeries and Descriptors inside of it for classes that hold multiple
lines at once.

.. moduleauthor:: Daniel Rodriguez

'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys

from .utils.py3 import map, range, string_types, with_metaclass

from .linebuffer import LineBuffer, LineActions, LinesOperation, LineDelay, NAN
from .lineroot import LineRoot, LineSingle, LineMultiple
from .metabase import AutoInfoClass
from . import metabase


class LineAlias(object):
    ''' Descriptor class that store a line reference and returns that line
    from the owner

    Keyword Args:
        line (int): reference to the line that will be returned from
        owner's *lines* buffer

    As a convenience the __set__ method of the descriptor is used not set
    the *line* reference because this is a constant along the live of the
    descriptor instance, but rather to set the value of the *line* at the
    instant '0' (the current one)
    '''

    def __init__(self, line):
        self.line = line

    def __get__(self, obj, cls=None):
        return obj.lines[self.line]

    def __set__(self, obj, value):
        '''
        A line cannot be "set" once it has been created. But the values
        inside the line can be "set". This is achieved by adding a binding
        to the line inside "value"
        '''
        if isinstance(value, LineMultiple):
            value = value.lines[0]

        # If the now for sure, LineBuffer 'value' is not a LineActions the
        # binding below could kick-in too early in the chain writing the value
        # into a not yet "forwarded" line, effectively writing the value 1
        # index too early and breaking the functionality (all in next mode)
        # Hence the need to transform it into a LineDelay object of null delay
        if not isinstance(value, LineActions):
            value = value(0)

        value.addbinding(obj.lines[self.line])


class Lines(object):
    '''
    Defines an "array" of lines which also has most of the interface of
    a LineBuffer class (forward, rewind, advance...).

    This interface operations are passed to the lines held by self

    The class can autosubclass itself (_derive) to hold new lines keeping them
    in the defined order.
    '''
    _getlinesbase = classmethod(lambda cls: ())
    _getlines = classmethod(lambda cls: ())
    _getlinesextra = classmethod(lambda cls: 0)
    _getlinesextrabase = classmethod(lambda cls: 0)

    @classmethod
    def _derive(cls, name, lines, extralines, otherbases, linesoverride=False,
                lalias=None):
        '''
        Creates a subclass of this class with the lines of this class as
        initial input for the subclass. It will include num "extralines" and
        lines present in "otherbases"

        "name" will be used as the suffix of the final class name

        "linesoverride": if True the lines of all bases will be discarded and
        the baseclass will be the topmost class "Lines". This is intended to
        create a new hierarchy
        '''
        obaseslines = ()
        obasesextralines = 0

        for otherbase in otherbases:
            if isinstance(otherbase, tuple):
                obaseslines += otherbase
            else:
                obaseslines += otherbase._getlines()
                obasesextralines += otherbase._getlinesextra()

        if not linesoverride:
            baselines = cls._getlines() + obaseslines
            baseextralines = cls._getlinesextra() + obasesextralines
        else:  # overriding lines, skip anything from baseclasses
            baselines = ()
            baseextralines = 0

        clslines = baselines + lines
        clsextralines = baseextralines + extralines
        lines2add = obaseslines + lines

        # str for Python 2/3 compatibility
        basecls = cls if not linesoverride else Lines

        newcls = type(str(cls.__name__ + '_' + name), (basecls,), {})
        clsmodule = sys.modules[cls.__module__]
        newcls.__module__ = cls.__module__
        setattr(clsmodule, str(cls.__name__ + '_' + name), newcls)

        setattr(newcls, '_getlinesbase', classmethod(lambda cls: baselines))
        setattr(newcls, '_getlines', classmethod(lambda cls: clslines))

        setattr(newcls, '_getlinesextrabase',
                classmethod(lambda cls: baseextralines))
        setattr(newcls, '_getlinesextra',
                classmethod(lambda cls: clsextralines))

        l2start = len(cls._getlines()) if not linesoverride else 0
        l2add = enumerate(lines2add, start=l2start)
        l2alias = {} if lalias is None else lalias._getkwargsdefault()
        for line, linealias in l2add:
            if not isinstance(linealias, string_types):
                # a tuple or list was passed, 1st is name
                linealias = linealias[0]

            desc = LineAlias(line)  # keep a reference below
            setattr(newcls, linealias, desc)

        # Create extra aliases for the given name, checking if the names is in
        # l2alias (which is from the argument lalias and comes from the
        # directive 'linealias', hence the confusion here (the LineAlias come
        # from the directive 'lines')
        for line, linealias in enumerate(newcls._getlines()):
            if not isinstance(linealias, string_types):
                # a tuple or list was passed, 1st is name
                linealias = linealias[0]

            desc = LineAlias(line)  # keep a reference below
            if linealias in l2alias:
                extranames = l2alias[linealias]
                if isinstance(linealias, string_types):
                    extranames = [extranames]

                for ename in extranames:
                    setattr(newcls, ename, desc)

        return newcls

    @classmethod
    def _getlinealias(cls, i):
        '''
        Return the alias for a line given the index
        '''
        lines = cls._getlines()
        if i >= len(lines):
            return ''
        linealias = lines[i]
        return linealias

    @classmethod
    def getlinealiases(cls):
        return cls._getlines()

    def itersize(self):
        return iter(self.lines[0:self.size()])

    def __init__(self, initlines=None):
        '''
        Create the lines recording during "_derive" or else use the
        provided "initlines"
        '''
        self.lines = list()
        for line, linealias in enumerate(self._getlines()):
            kwargs = dict()
            self.lines.append(LineBuffer(**kwargs))

        # Add the required extralines
        for i in range(self._getlinesextra()):
            if not initlines:
                self.lines.append(LineBuffer())
            else:
                self.lines.append(initlines[i])

    def __len__(self):
        '''
        Proxy line operation
        '''
        return len(self.lines[0])

    def size(self):
        return len(self.lines) - self._getlinesextra()

    def fullsize(self):
        return len(self.lines)

    def extrasize(self):
        return self._getlinesextra()

    def __getitem__(self, line):
        '''
        Proxy line operation
        '''
        return self.lines[line]

    def get(self, ago=0, size=1, line=0):
        '''
        Proxy line operation
        '''
        return self.lines[line].get(ago, size=size)

    def __setitem__(self, line, value):
        '''
        Proxy line operation
        '''
        setattr(self, self._getlinealias(line), value)

    def forward(self, value=NAN, size=1):
        '''
        Proxy line operation
        '''
        for line in self.lines:
            line.forward(value, size=size)

    def backwards(self, size=1, force=False):
        '''
        Proxy line operation
        '''
        for line in self.lines:
            line.backwards(size, force=force)

    def rewind(self, size=1):
        '''
        Proxy line operation
        '''
        for line in self.lines:
            line.rewind(size)

    def extend(self, value=NAN, size=0):
        '''
        Proxy line operation
        '''
        for line in self.lines:
            line.extend(value, size)

    def reset(self):
        '''
        Proxy line operation
        '''
        for line in self.lines:
            line.reset()

    def home(self):
        '''
        Proxy line operation
        '''
        for line in self.lines:
            line.home()

    def advance(self, size=1):
        '''
        Proxy line operation
        '''
        for line in self.lines:
            line.advance(size)

    def buflen(self, line=0):
        '''
        Proxy line operation
        '''
        return self.lines[line].buflen()


class MetaLineSeries(LineMultiple.__class__):
    '''
    Dirty job manager for a LineSeries

      - During __new__ (class creation), it reads "lines", "plotinfo",
        "plotlines" class variable definitions and turns them into
        Classes of type Lines or AutoClassInfo (plotinfo/plotlines)

      - During "new" (instance creation) the lines/plotinfo/plotlines
        classes are substituted in the instance with instances of the
        aforementioned classes and aliases are added for the "lines" held
        in the "lines" instance

        Additionally and for remaining kwargs, these are matched against
        args in plotinfo and if existent are set there and removed from kwargs

        Remember that this Metaclass has a MetaParams (from metabase)
        as root class and therefore "params" defined for the class have been
        removed from kwargs at an earlier state
    '''

    def __new__(meta, name, bases, dct):
        '''
        Intercept class creation, identifiy lines/plotinfo/plotlines class
        attributes and create corresponding classes for them which take over
        the class attributes
        '''

        # Get the aliases - don't leave it there for subclasses
        aliases = dct.setdefault('alias', ())
        aliased = dct.setdefault('aliased', '')

        # Remove the line definition (if any) from the class creation
        linesoverride = dct.pop('linesoverride', False)
        newlines = dct.pop('lines', ())
        extralines = dct.pop('extralines', 0)

        # remove the new plotinfo/plotlines definition if any
        newlalias = dict(dct.pop('linealias', {}))

        # remove the new plotinfo/plotlines definition if any
        newplotinfo = dict(dct.pop('plotinfo', {}))
        newplotlines = dict(dct.pop('plotlines', {}))

        # Create the class - pulling in any existing "lines"
        cls = super(MetaLineSeries, meta).__new__(meta, name, bases, dct)

        # Check the line aliases before creating the lines
        lalias = getattr(cls, 'linealias', AutoInfoClass)
        oblalias = [x.linealias for x in bases[1:] if hasattr(x, 'linealias')]
        cls.linealias = la = lalias._derive('la_' + name, newlalias, oblalias)

        # Get the actual lines or a default
        lines = getattr(cls, 'lines', Lines)

        # Create a subclass of the lines class with our name and newlines
        # and put it in the class
        morebaseslines = [x.lines for x in bases[1:] if hasattr(x, 'lines')]
        cls.lines = lines._derive(name, newlines, extralines, morebaseslines,
                                  linesoverride, lalias=la)

        # Get a copy from base class plotinfo/plotlines (created with the
        # class or set a default)
        plotinfo = getattr(cls, 'plotinfo', AutoInfoClass)
        plotlines = getattr(cls, 'plotlines', AutoInfoClass)

        # Create a plotinfo/plotlines subclass and set it in the class
        morebasesplotinfo = \
            [x.plotinfo for x in bases[1:] if hasattr(x, 'plotinfo')]
        cls.plotinfo = plotinfo._derive('pi_' + name, newplotinfo,
                                        morebasesplotinfo)

        # Before doing plotline newlines have been added and no plotlineinfo
        # is there add a default
        for line in newlines:
            newplotlines.setdefault(line, dict())

        morebasesplotlines = \
            [x.plotlines for x in bases[1:] if hasattr(x, 'plotlines')]
        cls.plotlines = plotlines._derive(
            'pl_' + name, newplotlines, morebasesplotlines, recurse=True)

        # create declared class aliases (a subclass with no modifications)
        for alias in aliases:
            newdct = {'__doc__': cls.__doc__,
                      '__module__': cls.__module__,
                      'aliased': cls.__name__}

            if not isinstance(alias, string_types):
                # a tuple or list was passed, 1st is name, 2nd plotname
                aliasplotname = alias[1]
                alias = alias[0]
                newdct['plotinfo'] = dict(plotname=aliasplotname)

            newcls = type(str(alias), (cls,), newdct)
            clsmodule = sys.modules[cls.__module__]
            setattr(clsmodule, alias, newcls)

        # return the class
        return cls

    def donew(cls, *args, **kwargs):
        '''
        Intercept instance creation, take over lines/plotinfo/plotlines
        class attributes by creating corresponding instance variables and add
        aliases for "lines" and the "lines" held within it
        '''
        # _obj.plotinfo shadows the plotinfo (class) definition in the class
        plotinfo = cls.plotinfo()

        for pname, pdef in cls.plotinfo._getitems():
            setattr(plotinfo, pname, kwargs.pop(pname, pdef))

        # Create the object and set the params in place
        _obj, args, kwargs = super(MetaLineSeries, cls).donew(*args, **kwargs)

        # set the plotinfo member in the class
        _obj.plotinfo = plotinfo

        # _obj.lines shadows the lines (class) definition in the class
        _obj.lines = cls.lines()

        # _obj.plotinfo shadows the plotinfo (class) definition in the class
        _obj.plotlines = cls.plotlines()

        # add aliases for lines and for the lines class itself
        _obj.l = _obj.lines
        if _obj.lines.fullsize():
            _obj.line = _obj.lines[0]

        for l, line in enumerate(_obj.lines):
            setattr(_obj, 'line_%s' % l, _obj._getlinealias(l))
            setattr(_obj, 'line_%d' % l, line)
            setattr(_obj, 'line%d' % l, line)

        # Parameter values have now been set before __init__
        return _obj, args, kwargs


class LineSeries(with_metaclass(MetaLineSeries, LineMultiple)):
    plotinfo = dict(
        plot=True,
        plotmaster=None,
        legendloc=None,
    )

    csv = True

    @property
    def array(self):
        return self.lines[0].array

    def __getattr__(self, name):
        # to refer to line by name directly if the attribute was not found
        # in this object if we set an attribute in this object it will be
        # found before we end up here
        return getattr(self.lines, name)

    def __len__(self):
        return len(self.lines)

    def __getitem__(self, key):
        return self.lines[0][key]

    def __setitem__(self, key, value):
        setattr(self.lines, self.lines._getlinealias(key), value)

    def __init__(self, *args, **kwargs):
        # if any args, kwargs make it up to here, something is broken
        # defining a __init__ guarantees the existence of im_func to findbases
        # in lineiterator later, because object.__init__ has no im_func
        # (object has slots)
        super(LineSeries, self).__init__()
        pass

    def plotlabel(self):
        label = self.plotinfo.plotname or self.__class__.__name__
        sublabels = self._plotlabel()
        if sublabels:
            for i, sublabel in enumerate(sublabels):
                # if isinstance(sublabel, LineSeries): ## DOESN'T WORK ???
                if hasattr(sublabel, 'plotinfo'):
                    try:
                        s = sublabel.plotinfo.plotname
                    except:
                        s = ''

                    sublabels[i] = s or sublabel.__name__

            label += ' (%s)' % ', '.join(map(str, sublabels))
        return label

    def _plotlabel(self):
        return self.params._getvalues()

    def _getline(self, line, minusall=False):
        if isinstance(line, string_types):
            lineobj = getattr(self.lines, line)
        else:
            if line == -1:  # restore original api behavior - default -> 0
                if minusall:  # minus means ... all lines
                    return None
                line = 0
            lineobj = self.lines[line]

        return lineobj

    def __call__(self, ago=None, line=-1):
        '''Returns either a delayed verison of itself in the form of a
        LineDelay object or a timeframe adapting version with regards to a ago

        Param: ago (default: None)

          If ago is None or an instance of LineRoot (a lines object) the
          returned valued is a LineCoupler instance

          If ago is anything else, it is assumed to be an int and a LineDelay
          object will be returned

        Param: line (default: -1)
          If a LinesCoupler will be returned ``-1`` means to return a
          LinesCoupler which adapts all lines of the current LineMultiple
          object. Else the appropriate line (referenced by name or index) will
          be LineCoupled

          If a LineDelay object will be returned, ``-1`` is the same as ``0``
          (to retain compatibility with the previous default value of 0). This
          behavior will change to return all existing lines in a LineDelayed
          form

          The referenced line (index or name) will be LineDelayed
        '''
        from .lineiterator import LinesCoupler  # avoid circular import

        if ago is None or isinstance(ago, LineRoot):
            args = [self, ago]
            lineobj = self._getline(line, minusall=True)
            if lineobj is not None:
                args[0] = lineobj

            return LinesCoupler(*args, _ownerskip=self)

        # else -> assume type(ago) == int -> return LineDelay object
        return LineDelay(self._getline(line), ago, _ownerskip=self)

    # The operations below have to be overriden to make sure subclasses can
    # reach them using "super" which will not call __getattr__ and
    # LineSeriesStub (see below) already uses super
    def forward(self, value=NAN, size=1):
        self.lines.forward(value, size)

    def backwards(self, size=1, force=False):
        self.lines.backwards(size, force=force)

    def rewind(self, size=1):
        self.lines.rewind(size)

    def extend(self, value=NAN, size=0):
        self.lines.extend(value, size)

    def reset(self):
        self.lines.reset()

    def home(self):
        self.lines.home()

    def advance(self, size=1):
        self.lines.advance(size)


class LineSeriesStub(LineSeries):
    '''Simulates a LineMultiple object based on LineSeries from a single line

    The index management operations are overriden to take into account if the
    line is a slave, ie:

      - The line reference is a line from many in a LineMultiple object
      - Both the LineMultiple object and the Line are managed by the same
        object

    Were slave not to be taken into account, the individual line would for
    example be advanced twice:

      - Once under when the LineMultiple object is advanced (because it
        advances all lines it is holding
      - Again as part of the regular management of the object holding it
    '''

    extralines = 1

    def __init__(self, line, slave=False):
        self.lines = self.__class__.lines(initlines=[line])
        # give a change to find the line owner (for plotting at least)
        self.owner = self._owner = line._owner
        self._minperiod = line._minperiod
        self.slave = slave

    # Only execute the operations below if the object is not a slave
    def forward(self, value=NAN, size=1):
        if not self.slave:
            super(LineSeriesStub, self).forward(value, size)

    def backwards(self, size=1, force=False):
        if not self.slave:
            super(LineSeriesStub, self).backwards(size, force=force)

    def rewind(self, size=1):
        if not self.slave:
            super(LineSeriesStub, self).rewind(size)

    def extend(self, value=NAN, size=0):
        if not self.slave:
            super(LineSeriesStub, self).extend(value, size)

    def reset(self):
        if not self.slave:
            super(LineSeriesStub, self).reset()

    def home(self):
        if not self.slave:
            super(LineSeriesStub, self).home()

    def advance(self, size=1):
        if not self.slave:
            super(LineSeriesStub, self).advance(size)

    def qbuffer(self):
        if not self.slave:
            super(LineSeriesStub, self).qbuffer()

    def minbuffer(self, size):
        if not self.slave:
            super(LineSeriesStub, self).minbuffer(size)


def LineSeriesMaker(arg, slave=False):
    if isinstance(arg, LineSeries):
        return arg

    return LineSeriesStub(arg, slave=slave)
