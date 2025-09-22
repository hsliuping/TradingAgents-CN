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

import collections
import datetime

import backtrader as bt
from backtrader.comminfo import CommInfoBase
from backtrader.order import Order, BuyOrder, SellOrder
from backtrader.position import Position
from backtrader.utils.py3 import string_types, integer_types

__all__ = ['BackBroker', 'BrokerBack']


class BackBroker(bt.BrokerBase):
    '''Broker Simulator

      The simulation supports different order types, checking a submitted order
      cash requirements against current cash, keeping track of cash and value
      for each iteration of ``cerebro`` and keeping the current position on
      different datas.

      *cash* is adjusted on each iteration for instruments like ``futures`` for
       which a price change implies in real brokers the addition/substracion of
       cash.

      Supported order types:

        - ``Market``: to be executed with the 1st tick of the next bar (namely
          the ``open`` price)

        - ``Close``: meant for intraday in which the order is executed with the
          closing price of the last bar of the session

        - ``Limit``: executes if the given limit price is seen during the
          session

        - ``Stop``: executes a ``Market`` order if the given stop price is seen

        - ``StopLimit``: sets a ``Limit`` order in motion if the given stop
          price is seen

      Because the broker is instantiated by ``Cerebro`` and there should be
      (mostly) no reason to replace the broker, the params are not controlled
      by the user for the instance.  To change this there are two options:

        1. Manually create an instance of this class with the desired params
           and use ``cerebro.broker = instance`` to set the instance as the
           broker for the ``run`` execution

        2. Use the ``set_xxx`` to set the value using
           ``cerebro.broker.set_xxx`` where ```xxx`` stands for the name of the
           parameter to set

        .. note::

           ``cerebro.broker`` is a *property* supported by the ``getbroker``
           and ``setbroker`` methods of ``Cerebro``

      Params:

        - ``cash`` (default: ``10000``): starting cash

        - ``commission`` (default: ``CommInfoBase(percabs=True)``)
          base commission scheme which applies to all assets

        - ``checksubmit`` (default: ``True``)
          check margin/cash before accepting an order into the system

        - ``eosbar`` (default: ``False``):
          With intraday bars consider a bar with the same ``time`` as the end
          of session to be the end of the session. This is not usually the
          case, because some bars (final auction) are produced by many
          exchanges for many products for a couple of minutes after the end of
          the session

        - ``filler`` (default: ``None``)

          A callable with signature: ``callable(order, price, ago)``

            - ``order``: obviously the order in execution. This provides access
              to the *data* (and with it the *ohlc* and *volume* values), the
              *execution type*, remaining size (``order.executed.remsize``) and
              others.

              Please check the ``Order`` documentation and reference for things
              available inside an ``Order`` instance

            - ``price`` the price at which the order is going to be executed in
              the ``ago`` bar

            - ``ago``: index meant to be used with ``order.data`` for the
              extraction of the *ohlc* and *volume* prices. In most cases this
              will be ``0`` but on a corner case for ``Close`` orders, this
              will be ``-1``.

              In order to get the bar volume (for example) do: ``volume =
              order.data.voluume[ago]``

          The callable must return the *executed size* (a value >= 0)

          The callable may of course be an object with ``__call__`` matching
          the aforementioned signature

          With the default ``None`` orders will be completely executed in a
          single shot

        - ``slip_perc`` (default: ``0.0``) Percentage in absolute termns (and
          positive) that should be used to slip prices up/down for buy/sell
          orders

          Note:

            - ``0.01`` is ``1%``

            - ``0.001`` is ``0.1%``

        - ``slip_fixed`` (default: ``0.0``) Percentage in units (and positive)
          that should be used to slip prices up/down for buy/sell orders

          Note: if ``slip_perc`` is non zero, it takes precendence over this.

        - ``slip_open`` (default: ``False``) whether to slip prices for order
          execution which would specifically used the *opening* price of the
          next bar. An example would be ``Market`` order which is executed with
          the next available tick, i.e: the opening price of the bar.

          This also applies to some of the other executions, because the logic
          tries to detect if the *opening* price would match the requested
          price/execution type when moving to a new bar.

        - ``slip_match`` (default: ``True``)

          If ``True`` the broker will offer a match by capping slippage at
          ``high/low`` prices in case they would be exceeded.

          If ``False`` the broker will not match the order with the current
          prices and will try execution during the next iteration

        - ``slip_limit`` (default: ``True``)

          ``Limit`` orders, given the exact match price requested, will be
          matched even if ``slip_match`` is ``False``.

          This option controls that behavior.

          If ``True``, then ``Limit`` orders will be matched by capping prices
          to the ``limit`` / ``high/low`` prices

          If ``False`` and slippage exceeds the cap, then there will be no
          match

        - ``slip_out`` (default: ``False``)

          Provide *slippage* even if the price falls outside the ``high`` -
          ``low`` range.

        - ``coc`` (default: ``False``)

          *Cheat-On-Close* Setting this to ``True`` with ``set_coc`` enables
           matching a ``Market`` order to the closing price of the bar in which
           the order was issued. This is actually *cheating*, because the bar
           is *closed* and any order should first be matched against the prices
           in the next bar

        - ``coo`` (default: ``False``)

          *Cheat-On-Open* Setting this to ``True`` with ``set_coo`` enables
           matching a ``Market`` order to the opening price, by for example
           using a timer with ``cheat`` set to ``True``, because such a timer
           gets executed before the broker has evaluated

        - ``int2pnl`` (default: ``True``)

          Assign generated interest (if any) to the profit and loss of
          operation that reduces a position (be it long or short). There may be
          cases in which this is undesired, because different strategies are
          competing and the interest would be assigned on a non-deterministic
          basis to any of them.

        - ``shortcash`` (default: ``True``)

          If True then cash will be increased when a stocklike asset is shorted
          and the calculated value for the asset will be negative.

          If ``False`` then the cash will be deducted as operation cost and the
          calculated value will be positive to end up with the same amount

        - ``fundstartval`` (default: ``100.0``)

          This parameter controls the start value for measuring the performance
          in a fund-like way, i.e.: cash can be added and deducted increasing
          the amount of shares. Performance is not measured using the net
          asset value of the porftoflio but using the value of the fund

        - ``fundmode`` (default: ``False``)

          If this is set to ``True`` analyzers like ``TimeReturn`` can
          automatically calculate returns based on the fund value and not on
          the total net asset value

    '''
    params = (
        ('cash', 10000.0),
        ('checksubmit', True),
        ('eosbar', False),
        ('filler', None),
        # slippage options
        ('slip_perc', 0.0),
        ('slip_fixed', 0.0),
        ('slip_open', False),
        ('slip_match', True),
        ('slip_limit', True),
        ('slip_out', False),
        ('coc', False),
        ('coo', False),
        ('int2pnl', True),
        ('shortcash', True),
        ('fundstartval', 100.0),
        ('fundmode', False),
    )

    def __init__(self):
        super(BackBroker, self).__init__()
        self._userhist = []
        self._fundhist = []
        # share_value, net asset value
        self._fhistlast = [float('NaN'), float('NaN')]

    def init(self):
        super(BackBroker, self).init()
        self.startingcash = self.cash = self.p.cash
        self._value = self.cash
        self._valuemkt = 0.0  # no open position

        self._valuelever = 0.0  # no open position
        self._valuemktlever = 0.0  # no open position

        self._leverage = 1.0  # initially nothing is open
        self._unrealized = 0.0  # no open position

        self.orders = list()  # will only be appending
        self.pending = collections.deque()  # popleft and append(right)
        self._toactivate = collections.deque()  # to activate in next cycle

        self.positions = collections.defaultdict(Position)
        self.d_credit = collections.defaultdict(float)  # credit per data
        self.notifs = collections.deque()

        self.submitted = collections.deque()

        # to keep dependent orders if needed
        self._pchildren = collections.defaultdict(collections.deque)

        self._ocos = dict()
        self._ocol = collections.defaultdict(list)

        self._fundval = self.p.fundstartval
        self._fundshares = self.p.cash / self._fundval
        self._cash_addition = collections.deque()

    def get_notification(self):
        try:
            return self.notifs.popleft()
        except IndexError:
            pass

        return None

    def set_fundmode(self, fundmode, fundstartval=None):
        '''Set the actual fundmode (True or False)

        If the argument fundstartval is not ``None``, it will used
        '''
        self.p.fundmode = fundmode
        if fundstartval is not None:
            self.set_fundstartval(fundstartval)

    def get_fundmode(self):
        '''Returns the actual fundmode (True or False)'''
        return self.p.fundmode

    fundmode = property(get_fundmode, set_fundmode)

    def set_fundstartval(self, fundstartval):
        '''Set the starting value of the fund-like performance tracker'''
        self.p.fundstartval = fundstartval

    def set_int2pnl(self, int2pnl):
        '''Configure assignment of interest to profit and loss'''
        self.p.int2pnl = int2pnl

    def set_coc(self, coc):
        '''Configure the Cheat-On-Close method to buy the close on order bar'''
        self.p.coc = coc

    def set_coo(self, coo):
        '''Configure the Cheat-On-Open method to buy the close on order bar'''
        self.p.coo = coo

    def set_shortcash(self, shortcash):
        '''Configure the shortcash parameters'''
        self.p.shortcash = shortcash

    def set_slippage_perc(self, perc,
                          slip_open=True, slip_limit=True,
                          slip_match=True, slip_out=False):
        '''Configure slippage to be percentage based'''
        self.p.slip_perc = perc
        self.p.slip_fixed = 0.0
        self.p.slip_open = slip_open
        self.p.slip_limit = slip_limit
        self.p.slip_match = slip_match
        self.p.slip_out = slip_out

    def set_slippage_fixed(self, fixed,
                           slip_open=True, slip_limit=True,
                           slip_match=True, slip_out=False):
        '''Configure slippage to be fixed points based'''
        self.p.slip_perc = 0.0
        self.p.slip_fixed = fixed
        self.p.slip_open = slip_open
        self.p.slip_limit = slip_limit
        self.p.slip_match = slip_match
        self.p.slip_out = slip_out

    def set_filler(self, filler):
        '''Sets a volume filler for volume filling execution'''
        self.p.filler = filler

    def set_checksubmit(self, checksubmit):
        '''Sets the checksubmit parameter'''
        self.p.checksubmit = checksubmit

    def set_eosbar(self, eosbar):
        '''Sets the eosbar parameter (alias: ``seteosbar``'''
        self.p.eosbar = eosbar

    seteosbar = set_eosbar

    def get_cash(self):
        '''Returns the current cash (alias: ``getcash``)'''
        return self.cash

    getcash = get_cash

    def set_cash(self, cash):
        '''Sets the cash parameter (alias: ``setcash``)'''
        self.startingcash = self.cash = self.p.cash = cash
        self._value = cash

    setcash = set_cash

    def add_cash(self, cash):
        '''Add/Remove cash to the system (use a negative value to remove)'''
        self._cash_addition.append(cash)

    def get_fundshares(self):
        '''Returns the current number of shares in the fund-like mode'''
        return self._fundshares

    fundshares = property(get_fundshares)

    def get_fundvalue(self):
        '''Returns the Fund-like share value'''
        return self._fundval

    fundvalue = property(get_fundvalue)

    def cancel(self, order, bracket=False):
        try:
            self.pending.remove(order)
        except ValueError:
            # If the list didn't have the element we didn't cancel anything
            return False

        order.cancel()
        self.notify(order)
        self._ococheck(order)
        if not bracket:
            self._bracketize(order, cancel=True)
        return True

    def get_value(self, datas=None, mkt=False, lever=False):
        '''Returns the portfolio value of the given datas (if datas is ``None``, then
        the total portfolio value will be returned (alias: ``getvalue``)
        '''
        if datas is None:
            if mkt:
                return self._valuemkt if not lever else self._valuemktlever

            return self._value if not lever else self._valuelever

        return self._get_value(datas=datas, lever=lever)

    getvalue = get_value

    def get_value_lever(self, datas=None, mkt=False):
        return self.get_value(datas=datas, mkt=mkt)

    def _get_value(self, datas=None, lever=False):
        pos_value = 0.0
        pos_value_unlever = 0.0
        unrealized = 0.0

        while self._cash_addition:
            c = self._cash_addition.popleft()
            self._fundshares += c / self._fundval
            self.cash += c

        for data in datas or self.positions:
            comminfo = self.getcommissioninfo(data)
            position = self.positions[data]
            # use valuesize:  returns raw value, rather than negative adj val
            if not self.p.shortcash:
                dvalue = comminfo.getvalue(position, data.close[0])
            else:
                dvalue = comminfo.getvaluesize(position.size, data.close[0])

            dunrealized = comminfo.profitandloss(position.size, position.price,
                                                 data.close[0])
            if datas and len(datas) == 1:
                if lever and dvalue > 0:
                    dvalue -= dunrealized
                    return (dvalue / comminfo.get_leverage()) + dunrealized
                return dvalue  # raw data value requested, short selling is neg

            if not self.p.shortcash:
                dvalue = abs(dvalue)  # short selling adds value in this case

            pos_value += dvalue
            unrealized += dunrealized

            if dvalue > 0:  # long position - unlever
                dvalue -= dunrealized
                pos_value_unlever += (dvalue / comminfo.get_leverage())
                pos_value_unlever += dunrealized
            else:
                pos_value_unlever += dvalue

        if not self._fundhist:
            self._value = v = self.cash + pos_value_unlever
            self._fundval = self._value / self._fundshares  # update fundvalue
        else:
            # Try to fetch a value
            fval, fvalue = self._process_fund_history()

            self._value = fvalue
            self.cash = fvalue - pos_value_unlever
            self._fundval = fval
            self._fundshares = fvalue / fval
            lev = pos_value / (pos_value_unlever or 1.0)

            # update the calculated values above to the historical values
            pos_value_unlever = fvalue
            pos_value = fvalue * lev

        self._valuemkt = pos_value_unlever

        self._valuelever = self.cash + pos_value
        self._valuemktlever = pos_value

        self._leverage = pos_value / (pos_value_unlever or 1.0)
        self._unrealized = unrealized

        return self._value if not lever else self._valuelever

    def get_leverage(self):
        return self._leverage

    def get_orders_open(self, safe=False):
        '''Returns an iterable with the orders which are still open (either not
        executed or partially executed

        The orders returned must not be touched.

        If order manipulation is needed, set the parameter ``safe`` to True
        '''
        if safe:
            os = [x.clone() for x in self.pending]
        else:
            os = [x for x in self.pending]

        return os

    def getposition(self, data):
        '''Returns the current position status (a ``Position`` instance) for
        the given ``data``'''
        return self.positions[data]

    def orderstatus(self, order):
        try:
            o = self.orders.index(order)
        except ValueError:
            o = order

        return o.status

    def _take_children(self, order):
        oref = order.ref
        pref = getattr(order.parent, 'ref', oref)  # parent ref or self

        if oref != pref:
            if pref not in self._pchildren:
                order.reject()  # parent not there - may have been rejected
                self.notify(order)  # reject child, notify
                return None

        return pref

    def submit(self, order, check=True):
        pref = self._take_children(order)
        if pref is None:  # order has not been taken
            return order

        pc = self._pchildren[pref]
        pc.append(order)  # store in parent/children queue

        if order.transmit:  # if single order, sent and queue cleared
            # if parent-child, the parent will be sent, the other kept
            rets = [self.transmit(x, check=check) for x in pc]
            return rets[-1]  # last one is the one triggering transmission

        return order

    def transmit(self, order, check=True):
        if check and self.p.checksubmit:
            order.submit()
            self.submitted.append(order)
            self.orders.append(order)
            self.notify(order)
        else:
            self.submit_accept(order)

        return order

    def check_submitted(self):
        cash = self.cash
        positions = dict()

        while self.submitted:
            order = self.submitted.popleft()

            if self._take_children(order) is None:  # children not taken
                continue

            comminfo = self.getcommissioninfo(order.data)

            position = positions.setdefault(
                order.data, self.positions[order.data].clone())

            # pseudo-execute the order to get the remaining cash after exec
            cash = self._execute(order, cash=cash, position=position)

            if cash >= 0.0:
                self.submit_accept(order)
                continue

            order.margin()
            self.notify(order)
            self._ococheck(order)
            self._bracketize(order, cancel=True)

    def submit_accept(self, order):
        order.pannotated = None
        order.submit()
        order.accept()
        self.pending.append(order)
        self.notify(order)

    def _bracketize(self, order, cancel=False):
        oref = order.ref
        pref = getattr(order.parent, 'ref', oref)
        parent = oref == pref

        pc = self._pchildren[pref]  # defdict - guaranteed
        if cancel or not parent:  # cancel left or child exec -> cancel other
            while pc:
                self.cancel(pc.popleft(), bracket=True)  # idempotent

            del self._pchildren[pref]  # defdict guaranteed

        else:  # not cancel -> parent exec'd
            pc.popleft()  # remove parent
            for o in pc:  # activate childnre
                self._toactivate.append(o)

    def _ococheck(self, order):
        # ocoref = self._ocos[order.ref] or order.ref  # a parent or self
        parentref = self._ocos[order.ref]
        ocoref = self._ocos.get(parentref, None)
        ocol = self._ocol.pop(ocoref, None)
        if ocol:
            for i in range(len(self.pending) - 1, -1, -1):
                o = self.pending[i]
                if o is not None and o.ref in ocol:
                    del self.pending[i]
                    o.cancel()
                    self.notify(o)

    def _ocoize(self, order, oco):
        oref = order.ref
        if oco is None:
            self._ocos[oref] = oref  # current order is parent
            self._ocol[oref].append(oref)  # create ocogroup
        else:
            ocoref = self._ocos[oco.ref]  # ref to group leader
            self._ocos[oref] = ocoref  # ref to group leader
            self._ocol[ocoref].append(oref)  # add to group

    def add_order_history(self, orders, notify=True):
        oiter = iter(orders)
        o = next(oiter, None)
        self._userhist.append([o, oiter, notify])

    def set_fund_history(self, fund):
        # iterable with the following pro item
        # [datetime, share_value, net asset value]
        fiter = iter(fund)
        f = list(next(fiter))  # must not be empty
        self._fundhist = [f, fiter]
        # self._fhistlast = f[1:]

        self.set_cash(float(f[2]))

    def buy(self, owner, data,
            size, price=None, plimit=None,
            exectype=None, valid=None, tradeid=0, oco=None,
            trailamount=None, trailpercent=None,
            parent=None, transmit=True,
            histnotify=False, _checksubmit=True,
            **kwargs):

        order = BuyOrder(owner=owner, data=data,
                         size=size, price=price, pricelimit=plimit,
                         exectype=exectype, valid=valid, tradeid=tradeid,
                         trailamount=trailamount, trailpercent=trailpercent,
                         parent=parent, transmit=transmit,
                         histnotify=histnotify)

        order.addinfo(**kwargs)
        self._ocoize(order, oco)

        return self.submit(order, check=_checksubmit)

    def sell(self, owner, data,
             size, price=None, plimit=None,
             exectype=None, valid=None, tradeid=0, oco=None,
             trailamount=None, trailpercent=None,
             parent=None, transmit=True,
             histnotify=False, _checksubmit=True,
             **kwargs):

        order = SellOrder(owner=owner, data=data,
                          size=size, price=price, pricelimit=plimit,
                          exectype=exectype, valid=valid, tradeid=tradeid,
                          trailamount=trailamount, trailpercent=trailpercent,
                          parent=parent, transmit=transmit,
                          histnotify=histnotify)

        order.addinfo(**kwargs)
        self._ocoize(order, oco)

        return self.submit(order, check=_checksubmit)

    def _execute(self, order, ago=None, price=None, cash=None, position=None,
                 dtcoc=None):
        # ago = None is used a flag for pseudo execution
        if ago is not None and price is None:
            return  # no psuedo exec no price - no execution

        if self.p.filler is None or ago is None:
            # Order gets full size or pseudo-execution
            size = order.executed.remsize
        else:
            # Execution depends on volume filler
            size = self.p.filler(order, price, ago)
            if not order.isbuy():
                size = -size

        # Get comminfo object for the data
        comminfo = self.getcommissioninfo(order.data)

        # Check if something has to be compensated
        if order.data._compensate is not None:
            data = order.data._compensate
            cinfocomp = self.getcommissioninfo(data)  # for actual commission
        else:
            data = order.data
            cinfocomp = comminfo

        # Adjust position with operation size
        if ago is not None:
            # Real execution with date
            position = self.positions[data]
            pprice_orig = position.price

            psize, pprice, opened, closed = position.pseudoupdate(size, price)

            # if part/all of a position has been closed, then there has been
            # a profitandloss ... record it
            pnl = comminfo.profitandloss(-closed, pprice_orig, price)
            cash = self.cash
        else:
            pnl = 0
            if not self.p.coo:
                price = pprice_orig = order.created.price
            else:
                # When doing cheat on open, the price to be considered for a
                # market order is the opening price and not the default closing
                # price with which the order was created
                if order.exectype == Order.Market:
                    price = pprice_orig = order.data.open[0]
                else:
                    price = pprice_orig = order.created.price

            psize, pprice, opened, closed = position.update(size, price)

        # "Closing" totally or partially is possible. Cash may be re-injected
        if closed:
            # Adjust to returned value for closed items & acquired opened items
            if self.p.shortcash:
                closedvalue = comminfo.getvaluesize(-closed, pprice_orig)
            else:
                closedvalue = comminfo.getoperationcost(closed, pprice_orig)

            closecash = closedvalue
            if closedvalue > 0:  # long position closed
                closecash /= comminfo.get_leverage()  # inc cash with lever

            cash += closecash + pnl * comminfo.stocklike
            # Calculate and substract commission
            closedcomm = comminfo.getcommission(closed, price)
            cash -= closedcomm

            if ago is not None:
                # Cashadjust closed contracts: prev close vs exec price
                # The operation can inject or take cash out
                cash += comminfo.cashadjust(-closed,
                                            position.adjbase,
                                            price)

                # Update system cash
                self.cash = cash
        else:
            closedvalue = closedcomm = 0.0

        popened = opened
        if opened:
            if self.p.shortcash:
                openedvalue = comminfo.getvaluesize(opened, price)
            else:
                openedvalue = comminfo.getoperationcost(opened, price)

            opencash = openedvalue
            if openedvalue > 0:  # long position being opened
                opencash /= comminfo.get_leverage()  # dec cash with level

            cash -= opencash  # original behavior

            openedcomm = cinfocomp.getcommission(opened, price)
            cash -= openedcomm

            if cash < 0.0:
                # execution is not possible - nullify
                opened = 0
                openedvalue = openedcomm = 0.0

            elif ago is not None:  # real execution
                if abs(psize) > abs(opened):
                    # some futures were opened - adjust the cash of the
                    # previously existing futures to the operation price and
                    # use that as new adjustment base, because it already is
                    # for the new futures At the end of the cycle the
                    # adjustment to the close price will be done for all open
                    # futures from a common base price with regards to the
                    # close price
                    adjsize = psize - opened
                    cash += comminfo.cashadjust(adjsize,
                                                position.adjbase, price)

                # record adjust price base for end of bar cash adjustment
                position.adjbase = price

                # update system cash - checking if opened is still != 0
                self.cash = cash
        else:
            openedvalue = openedcomm = 0.0

        if ago is None:
            # return cash from pseudo-execution
            return cash

        execsize = closed + opened

        if execsize:
            # Confimrm the operation to the comminfo object
            comminfo.confirmexec(execsize, price)

            # do a real position update if something was executed
            position.update(execsize, price, data.datetime.datetime())

            if closed and self.p.int2pnl:  # Assign accumulated interest data
                closedcomm += self.d_credit.pop(data, 0.0)

            # Execute and notify the order
            order.execute(dtcoc or data.datetime[ago],
                          execsize, price,
                          closed, closedvalue, closedcomm,
                          opened, openedvalue, openedcomm,
                          comminfo.margin, pnl,
                          psize, pprice)

            order.addcomminfo(comminfo)

            self.notify(order)
            self._ococheck(order)

        if popened and not opened:
            # opened was not executed - not enough cash
            order.margin()
            self.notify(order)
            self._ococheck(order)
            self._bracketize(order, cancel=True)

    def notify(self, order):
        self.notifs.append(order.clone())

    def _try_exec_historical(self, order):
        self._execute(order, ago=0, price=order.created.price)

    def _try_exec_market(self, order, popen, phigh, plow):
        ago = 0
        if self.p.coc and order.info.get('coc', True):
            dtcoc = order.created.dt
            exprice = order.created.pclose
        else:
            if not self.p.coo and order.data.datetime[0] <= order.created.dt:
                return    # can only execute after creation time

            dtcoc = None
            exprice = popen

        if order.isbuy():
            p = self._slip_up(phigh, exprice, doslip=self.p.slip_open)
        else:
            p = self._slip_down(plow, exprice, doslip=self.p.slip_open)

        self._execute(order, ago=0, price=p, dtcoc=dtcoc)

    def _try_exec_close(self, order, pclose):
        # pannotated allows to keep track of the closing bar if there is no
        # information which lets us know that the current bar is the closing
        # bar (like matching end of session bar)
        # The actual matching will be done one bar afterwards but using the
        # information from the actual closing bar

        dt0 = order.data.datetime[0]
        # don't use "len" -> in replay the close can be reached with same len
        if dt0 > order.created.dt:  # can only execute after creation time
            # or (self.p.eosbar and dt0 == order.dteos):
            if dt0 >= order.dteos:
                # past the end of session or right at it and eosbar is True
                if order.pannotated and dt0 > order.dteos:
                    ago = -1
                    execprice = order.pannotated
                else:
                    ago = 0
                    execprice = pclose

                self._execute(order, ago=ago, price=execprice)
                return

        # If no exexcution has taken place ... annotate the closing price
        order.pannotated = pclose

    def _try_exec_limit(self, order, popen, phigh, plow, plimit):
        if order.isbuy():
            if plimit >= popen:
                # open smaller/equal than requested - buy cheaper
                pmax = min(phigh, plimit)
                p = self._slip_up(pmax, popen, doslip=self.p.slip_open,
                                  lim=True)
                self._execute(order, ago=0, price=p)
            elif plimit >= plow:
                # day low below req price ... match limit price
                self._execute(order, ago=0, price=plimit)

        else:  # Sell
            if plimit <= popen:
                # open greater/equal than requested - sell more expensive
                pmin = max(plow, plimit)
                p = self._slip_down(plimit, popen, doslip=self.p.slip_open,
                                    lim=True)
                self._execute(order, ago=0, price=p)
            elif plimit <= phigh:
                # day high above req price ... match limit price
                self._execute(order, ago=0, price=plimit)

    def _try_exec_stop(self, order, popen, phigh, plow, pcreated, pclose):
        if order.isbuy():
            if popen >= pcreated:
                # price penetrated with an open gap - use open
                p = self._slip_up(phigh, popen, doslip=self.p.slip_open)
                self._execute(order, ago=0, price=p)
            elif phigh >= pcreated:
                # price penetrated during the session - use trigger price
                p = self._slip_up(phigh, pcreated)
                self._execute(order, ago=0, price=p)

        else:  # Sell
            if popen <= pcreated:
                # price penetrated with an open gap - use open
                p = self._slip_down(plow, popen, doslip=self.p.slip_open)
                self._execute(order, ago=0, price=p)
            elif plow <= pcreated:
                # price penetrated during the session - use trigger price
                p = self._slip_down(plow, pcreated)
                self._execute(order, ago=0, price=p)

        # not (completely) executed and trailing stop
        if order.alive() and order.exectype == Order.StopTrail:
            order.trailadjust(pclose)

    def _try_exec_stoplimit(self, order,
                            popen, phigh, plow, pclose,
                            pcreated, plimit):
        if order.isbuy():
            if popen >= pcreated:
                order.triggered = True
                self._try_exec_limit(order, popen, phigh, plow, plimit)

            elif phigh >= pcreated:
                # price penetrated upwards during the session
                order.triggered = True
                # can calculate execution for a few cases - datetime is fixed
                if popen > pclose:
                    if plimit >= pcreated:  # limit above stop trigger
                        p = self._slip_up(phigh, pcreated, lim=True)
                        self._execute(order, ago=0, price=p)
                    elif plimit >= pclose:
                        self._execute(order, ago=0, price=plimit)
                else:  # popen < pclose
                    if plimit >= pcreated:
                        p = self._slip_up(phigh, pcreated, lim=True)
                        self._execute(order, ago=0, price=p)
        else:  # Sell
            if popen <= pcreated:
                # price penetrated downwards with an open gap
                order.triggered = True
                self._try_exec_limit(order, popen, phigh, plow, plimit)

            elif plow <= pcreated:
                # price penetrated downwards during the session
                order.triggered = True
                # can calculate execution for a few cases - datetime is fixed
                if popen <= pclose:
                    if plimit <= pcreated:
                        p = self._slip_down(plow, pcreated, lim=True)
                        self._execute(order, ago=0, price=p)
                    elif plimit <= pclose:
                        self._execute(order, ago=0, price=plimit)
                else:
                    # popen > pclose
                    if plimit <= pcreated:
                        p = self._slip_down(plow, pcreated, lim=True)
                        self._execute(order, ago=0, price=p)

        # not (completely) executed and trailing stop
        if order.alive() and order.exectype == Order.StopTrailLimit:
            order.trailadjust(pclose)

    def _slip_up(self, pmax, price, doslip=True, lim=False):
        if not doslip:
            return price

        slip_perc = self.p.slip_perc
        slip_fixed = self.p.slip_fixed
        if slip_perc:
            pslip = price * (1 + slip_perc)
        elif slip_fixed:
            pslip = price + slip_fixed
        else:
            return price

        if pslip <= pmax:  # slipping can return price
            return pslip
        elif self.p.slip_match or (lim and self.p.slip_limit):
            if not self.p.slip_out:
                return pmax

            return pslip  # non existent price

        return None  # no price can be returned

    def _slip_down(self, pmin, price, doslip=True, lim=False):
        if not doslip:
            return price

        slip_perc = self.p.slip_perc
        slip_fixed = self.p.slip_fixed
        if slip_perc:
            pslip = price * (1 - slip_perc)
        elif slip_fixed:
            pslip = price - slip_fixed
        else:
            return price

        if pslip >= pmin:  # slipping can return price
            return pslip
        elif self.p.slip_match or (lim and self.p.slip_limit):
            if not self.p.slip_out:
                return pmin

            return pslip  # non existent price

        return None  # no price can be returned

    def _try_exec(self, order):
        data = order.data

        popen = getattr(data, 'tick_open', None)
        if popen is None:
            popen = data.open[0]
        phigh = getattr(data, 'tick_high', None)
        if phigh is None:
            phigh = data.high[0]
        plow = getattr(data, 'tick_low', None)
        if plow is None:
            plow = data.low[0]
        pclose = getattr(data, 'tick_close', None)
        if pclose is None:
            pclose = data.close[0]

        pcreated = order.created.price
        plimit = order.created.pricelimit

        if order.exectype == Order.Market:
            self._try_exec_market(order, popen, phigh, plow)

        elif order.exectype == Order.Close:
            self._try_exec_close(order, pclose)

        elif order.exectype == Order.Limit:
            self._try_exec_limit(order, popen, phigh, plow, pcreated)

        elif (order.triggered and
              order.exectype in [Order.StopLimit, Order.StopTrailLimit]):
            self._try_exec_limit(order, popen, phigh, plow, plimit)

        elif order.exectype in [Order.Stop, Order.StopTrail]:
            self._try_exec_stop(order, popen, phigh, plow, pcreated, pclose)

        elif order.exectype in [Order.StopLimit, Order.StopTrailLimit]:
            self._try_exec_stoplimit(order,
                                     popen, phigh, plow, pclose,
                                     pcreated, plimit)

        elif order.exectype == Order.Historical:
            self._try_exec_historical(order)

    def _process_fund_history(self):
        fhist = self._fundhist  # [last element, iterator]
        f, funds = fhist
        if not f:
            return self._fhistlast

        dt = f[0]  # date/datetime instance
        if isinstance(dt, string_types):
            dtfmt = '%Y-%m-%d'
            if 'T' in dt:
                dtfmt += 'T%H:%M:%S'
                if '.' in dt:
                    dtfmt += '.%f'
            dt = datetime.datetime.strptime(dt, dtfmt)
            f[0] = dt  # update value

        elif isinstance(dt, datetime.datetime):
            pass
        elif isinstance(dt, datetime.date):
            dt = datetime.datetime(year=dt.year, month=dt.month, day=dt.day)
            f[0] = dt  # Update the value

        # Synchronization with the strategy is not possible because the broker
        # is called before the strategy advances. The 2 lines below would do it
        # if possible
        # st0 = self.cerebro.runningstrats[0]
        # if dt <= st0.datetime.datetime():
        if dt <= self.cerebro._dtmaster:
            self._fhistlast = f[1:]
            fhist[0] = list(next(funds, []))

        return self._fhistlast

    def _process_order_history(self):
        for uhist in self._userhist:
            uhorder, uhorders, uhnotify = uhist
            while uhorder is not None:
                uhorder = list(uhorder)  # to support assignment (if tuple)
                try:
                    dataidx = uhorder[3]  # 2nd field
                except IndexError:
                    dataidx = None  # Field not present, use default

                if dataidx is None:
                    d = self.cerebro.datas[0]
                elif isinstance(dataidx, integer_types):
                    d = self.cerebro.datas[dataidx]
                else:  # assume string
                    d = self.cerebro.datasbyname[dataidx]

                if not len(d):
                    break  # may start later as oter data feeds

                dt = uhorder[0]  # date/datetime instance
                if isinstance(dt, string_types):
                    dtfmt = '%Y-%m-%d'
                    if 'T' in dt:
                        dtfmt += 'T%H:%M:%S'
                        if '.' in dt:
                            dtfmt += '.%f'
                    dt = datetime.datetime.strptime(dt, dtfmt)
                    uhorder[0] = dt
                elif isinstance(dt, datetime.datetime):
                    pass
                elif isinstance(dt, datetime.date):
                    dt = datetime.datetime(year=dt.year,
                                           month=dt.month,
                                           day=dt.day)
                    uhorder[0] = dt

                if dt > d.datetime.datetime():
                    break  # cannot execute yet 1st in queue, stop processing

                size = uhorder[1]
                price = uhorder[2]
                owner = self.cerebro.runningstrats[0]
                if size > 0:
                    o = self.buy(owner=owner, data=d,
                                 size=size, price=price,
                                 exectype=Order.Historical,
                                 histnotify=uhnotify,
                                 _checksubmit=False)

                elif size < 0:
                    o = self.sell(owner=owner, data=d,
                                  size=abs(size), price=price,
                                  exectype=Order.Historical,
                                  histnotify=uhnotify,
                                  _checksubmit=False)

                # update to next potential order
                uhist[0] = uhorder = next(uhorders, None)

    def next(self):
        while self._toactivate:
            self._toactivate.popleft().activate()

        if self.p.checksubmit:
            self.check_submitted()

        # Discount any cash for positions hold
        credit = 0.0
        for data, pos in self.positions.items():
            if pos:
                comminfo = self.getcommissioninfo(data)
                dt0 = data.datetime.datetime()
                dcredit = comminfo.get_credit_interest(data, pos, dt0)
                self.d_credit[data] += dcredit
                credit += dcredit
                pos.datetime = dt0  # mark last credit operation

        self.cash -= credit

        self._process_order_history()

        # Iterate once over all elements of the pending queue
        self.pending.append(None)
        while True:
            order = self.pending.popleft()
            if order is None:
                break

            if order.expire():
                self.notify(order)
                self._ococheck(order)
                self._bracketize(order, cancel=True)

            elif not order.active():
                self.pending.append(order)  # cannot yet be processed

            else:
                self._try_exec(order)
                if order.alive():
                    self.pending.append(order)

                elif order.status == Order.Completed:
                    # a bracket parent order may have been executed
                    self._bracketize(order)

        # Operations have been executed ... adjust cash end of bar
        for data, pos in self.positions.items():
            # futures change cash every bar
            if pos:
                comminfo = self.getcommissioninfo(data)
                self.cash += comminfo.cashadjust(pos.size,
                                                 pos.adjbase,
                                                 data.close[0])
                # record the last adjustment price
                pos.adjbase = data.close[0]

        self._get_value()  # update value


# Alias
BrokerBack = BackBroker
