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

from backtrader.comminfo import CommInfoBase
from backtrader.metabase import MetaParams
from backtrader.utils.py3 import with_metaclass

from . import fillers as fillers
from . import fillers as filler


class MetaBroker(MetaParams):
    def __init__(cls, name, bases, dct):
        '''
        Class has already been created ... fill missing methods if needed be
        '''
        # Initialize the class
        super(MetaBroker, cls).__init__(name, bases, dct)
        translations = {
            'get_cash': 'getcash',
            'get_value': 'getvalue',
        }

        for attr, trans in translations.items():
            if not hasattr(cls, attr):
                setattr(cls, name, getattr(cls, trans))


class BrokerBase(with_metaclass(MetaBroker, object)):
    params = (
        ('commission', CommInfoBase(percabs=True)),
    )

    def __init__(self):
        self.comminfo = dict()
        self.init()

    def init(self):
        # called from init and from start
        if None not in self.comminfo:
            self.comminfo = dict({None: self.p.commission})

    def start(self):
        self.init()

    def stop(self):
        pass

    def add_order_history(self, orders, notify=False):
        '''Add order history. See cerebro for details'''
        raise NotImplementedError

    def set_fund_history(self, fund):
        '''Add fund history. See cerebro for details'''
        raise NotImplementedError

    def getcommissioninfo(self, data):
        '''Retrieves the ``CommissionInfo`` scheme associated with the given
        ``data``'''
        if data._name in self.comminfo:
            return self.comminfo[data._name]

        return self.comminfo[None]

    def setcommission(self,
                      commission=0.0, margin=None, mult=1.0,
                      commtype=None, percabs=True, stocklike=False,
                      interest=0.0, interest_long=False, leverage=1.0,
                      automargin=False,
                      name=None):

        '''This method sets a `` CommissionInfo`` object for assets managed in
        the broker with the parameters. Consult the reference for
        ``CommInfoBase``

        If name is ``None``, this will be the default for assets for which no
        other ``CommissionInfo`` scheme can be found
        '''

        comm = CommInfoBase(commission=commission, margin=margin, mult=mult,
                            commtype=commtype, stocklike=stocklike,
                            percabs=percabs,
                            interest=interest, interest_long=interest_long,
                            leverage=leverage, automargin=automargin)
        self.comminfo[name] = comm

    def addcommissioninfo(self, comminfo, name=None):
        '''Adds a ``CommissionInfo`` object that will be the default for all assets if
        ``name`` is ``None``'''
        self.comminfo[name] = comminfo

    def getcash(self):
        raise NotImplementedError

    def getvalue(self, datas=None):
        raise NotImplementedError

    def get_fundshares(self):
        '''Returns the current number of shares in the fund-like mode'''
        return 1.0  # the abstract mode has only 1 share

    fundshares = property(get_fundshares)

    def get_fundvalue(self):
        return self.getvalue()

    fundvalue = property(get_fundvalue)

    def set_fundmode(self, fundmode, fundstartval=None):
        '''Set the actual fundmode (True or False)

        If the argument fundstartval is not ``None``, it will used
        '''
        pass  # do nothing, not all brokers can support this

    def get_fundmode(self):
        '''Returns the actual fundmode (True or False)'''
        return False

    fundmode = property(get_fundmode, set_fundmode)

    def getposition(self, data):
        raise NotImplementedError

    def submit(self, order):
        raise NotImplementedError

    def cancel(self, order):
        raise NotImplementedError

    def buy(self, owner, data, size, price=None, plimit=None,
            exectype=None, valid=None, tradeid=0, oco=None,
            trailamount=None, trailpercent=None,
            **kwargs):

        raise NotImplementedError

    def sell(self, owner, data, size, price=None, plimit=None,
             exectype=None, valid=None, tradeid=0, oco=None,
             trailamount=None, trailpercent=None,
             **kwargs):

        raise NotImplementedError

    def next(self):
        pass

# __all__ = ['BrokerBase', 'fillers', 'filler']
