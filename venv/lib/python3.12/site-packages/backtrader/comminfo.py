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

import datetime

from .utils.py3 import with_metaclass
from .metabase import MetaParams


class CommInfoBase(with_metaclass(MetaParams)):
    '''Base Class for the Commission Schemes.

    Params:

      - ``commission`` (def: ``0.0``): base commission value in percentage or
        monetary units

      - ``mult`` (def ``1.0``): multiplier applied to the asset for
        value/profit

      - ``margin`` (def: ``None``): amount of monetary units needed to
        open/hold an operation. It only applies if the final ``_stocklike``
        attribute in the class is set to ``False``

      - ``automargin`` (def: ``False``): Used by the method ``get_margin``
        to automatically calculate the margin/guarantees needed with the
        following policy

          - Use param ``margin`` if param ``automargin`` evaluates to ``False``

          - Use param ``mult`` * ``price`` if ``automargin < 0``

          - Use param ``automargin`` * ``price`` if ``automargin > 0``

      - ``commtype`` (def: ``None``): Supported values are
        ``CommInfoBase.COMM_PERC`` (commission to be understood as %) and
        ``CommInfoBase.COMM_FIXED`` (commission to be understood as monetary
        units)

        The default value of ``None`` is a supported value to retain
        compatibility with the legacy ``CommissionInfo`` object. If
        ``commtype`` is set to None, then the following applies:

          - ``margin`` is ``None``: Internal ``_commtype`` is set to
            ``COMM_PERC`` and ``_stocklike`` is set to ``True`` (Operating
            %-wise with Stocks)

          - ``margin`` is not ``None``: ``_commtype`` set to ``COMM_FIXED`` and
            ``_stocklike`` set to ``False`` (Operating with fixed rount-trip
            commission with Futures)

        If this param is set to something else than ``None``, then it will be
        passed to the internal ``_commtype`` attribute and the same will be
        done with the param ``stocklike`` and the internal attribute
        ``_stocklike``

      - ``stocklike`` (def: ``False``): Indicates if the instrument is
        Stock-like or Futures-like (see the ``commtype`` discussion above)

      - ``percabs`` (def: ``False``): when ``commtype`` is set to COMM_PERC,
        whether the parameter ``commission`` has to be understood as XX% or
        0.XX

        If this param is ``True``: 0.XX
        If this param is ``False``: XX%

      - ``interest`` (def: ``0.0``)

        If this is non-zero, this is the yearly interest charged for holding a
        short selling position. This is mostly meant for stock short-selling

        The formula: ``days * price * abs(size) * (interest / 365)``

        It must be specified in absolute terms: 0.05 -> 5%

        .. note:: the behavior can be changed by overriding the method:
                 ``_get_credit_interest``

      - ``interest_long`` (def: ``False``)

        Some products like ETFs get charged on interest for short and long
        positions. If ths is ``True`` and ``interest`` is non-zero the interest
        will be charged on both directions

      - ``leverage`` (def: ``1.0``)

        Amount of leverage for the asset with regards to the needed cash

    Attributes:

      - ``_stocklike``: Final value to use for Stock-like/Futures-like behavior
      - ``_commtype``: Final value to use for PERC vs FIXED commissions

      This two are used internally instead of the declared params to enable the
      compatibility check described above for the legacy ``CommissionInfo``
      object

    '''

    COMM_PERC, COMM_FIXED = range(2)

    params = (
        ('commission', 0.0), ('mult', 1.0), ('margin', None),
        ('commtype', None),
        ('stocklike', False),
        ('percabs', False),
        ('interest', 0.0),
        ('interest_long', False),
        ('leverage', 1.0),
        ('automargin', False),
    )

    def __init__(self):
        super(CommInfoBase, self).__init__()

        self._stocklike = self.p.stocklike
        self._commtype = self.p.commtype

        # The intial block checks for the behavior of the original
        # CommissionInfo in which the commission scheme (perc/fixed) was
        # determined by parameter "margin" evaluating to False/True
        # If the parameter "commtype" is None, this behavior is emulated
        # else, the parameter values are used

        if self._commtype is None:  # original CommissionInfo behavior applies
            if self.p.margin:
                self._stocklike = False
                self._commtype = self.COMM_FIXED
            else:
                self._stocklike = True
                self._commtype = self.COMM_PERC

        if not self._stocklike and not self.p.margin:
            self.p.margin = 1.0  # avoid having None/0

        if self._commtype == self.COMM_PERC and not self.p.percabs:
            self.p.commission /= 100.0

        self._creditrate = self.p.interest / 365.0

    @property
    def margin(self):
        return self.p.margin

    @property
    def stocklike(self):
        return self._stocklike

    def get_margin(self, price):
        '''Returns the actual margin/guarantees needed for a single item of the
        asset at the given price. The default implementation has this policy:

          - Use param ``margin`` if param ``automargin`` evaluates to ``False``

          - Use param ``mult`` * ``price`` if ``automargin < 0``

          - Use param ``automargin`` * ``price`` if ``automargin > 0``
        '''
        if not self.p.automargin:
            return self.p.margin

        elif self.p.automargin < 0:
            return price * self.p.mult

        return price * self.p.automargin  # int/float expected

    def get_leverage(self):

        '''Returns the level of leverage allowed for this comission scheme'''
        return self.p.leverage

    def getsize(self, price, cash):
        '''Returns the needed size to meet a cash operation at a given price'''
        if not self._stocklike:
            return int(self.p.leverage * (cash // self.get_margin(price)))

        return int(self.p.leverage * (cash // price))

    def getoperationcost(self, size, price):
        '''Returns the needed amount of cash an operation would cost'''
        if not self._stocklike:
            return abs(size) * self.get_margin(price)

        return abs(size) * price

    def getvaluesize(self, size, price):
        '''Returns the value of size for given a price. For future-like
        objects it is fixed at size * margin'''
        if not self._stocklike:
            return abs(size) * self.get_margin(price)

        return size * price

    def getvalue(self, position, price):
        '''Returns the value of a position given a price. For future-like
        objects it is fixed at size * margin'''
        if not self._stocklike:
            return abs(position.size) * self.get_margin(price)

        size = position.size
        if size >= 0:
            return size * price

        # With stocks, a short position is worth more as the price goes down
        value = position.price * size  # original value
        value += (position.price - price) * size  # increased value
        return value

    def _getcommission(self, size, price, pseudoexec):
        '''Calculates the commission of an operation at a given price

        pseudoexec: if True the operation has not yet been executed
        '''
        if self._commtype == self.COMM_PERC:
            return abs(size) * self.p.commission * price

        return abs(size) * self.p.commission

    def getcommission(self, size, price):
        '''Calculates the commission of an operation at a given price
        '''
        return self._getcommission(size, price, pseudoexec=True)

    def confirmexec(self, size, price):
        return self._getcommission(size, price, pseudoexec=False)

    def profitandloss(self, size, price, newprice):
        '''Return actual profit and loss a position has'''
        return size * (newprice - price) * self.p.mult

    def cashadjust(self, size, price, newprice):
        '''Calculates cash adjustment for a given price difference'''
        if not self._stocklike:
            return size * (newprice - price) * self.p.mult

        return 0.0

    def get_credit_interest(self, data, pos, dt):
        '''Calculates the credit due for short selling or product specific'''
        size, price = pos.size, pos.price

        if size > 0 and not self.p.interest_long:
            return 0.0  # long positions not charged

        dt0 = dt.date()
        dt1 = pos.datetime.date()

        if dt0 <= dt1:
            return 0.0

        return self._get_credit_interest(data, size, price,
                                         (dt0 - dt1).days, dt0, dt1)

    def _get_credit_interest(self, data, size, price, days, dt0, dt1):
        '''
        This method returns  the cost in terms of credit interest charged by
        the broker.

        In the case of ``size > 0`` this method will only be called if the
        parameter to the class ``interest_long`` is ``True``

        The formulat for the calculation of the credit interest rate is:

          The formula: ``days * price * abs(size) * (interest / 365)``


        Params:
          - ``data``: data feed for which interest is charged

          - ``size``: current position size. > 0 for long positions and < 0 for
            short positions (this parameter will not be ``0``)

          - ``price``: current position price

          - ``days``: number of days elapsed since last credit calculation
            (this is (dt0 - dt1).days)

          - ``dt0``: (datetime.datetime) current datetime

          - ``dt1``: (datetime.datetime) datetime of previous calculation

        ``dt0`` and ``dt1`` are not used in the default implementation and are
        provided as extra input for overridden methods
        '''
        return days * self._creditrate * abs(size) * price


class CommissionInfo(CommInfoBase):
    '''Base Class for the actual Commission Schemes.

    CommInfoBase was created to keep suppor for the original, incomplete,
    support provided by *backtrader*. New commission schemes derive from this
    class which subclasses ``CommInfoBase``.

    The default value of ``percabs`` is also changed to ``True``

    Params:

      - ``percabs`` (def: True): when ``commtype`` is set to COMM_PERC, whether
        the parameter ``commission`` has to be understood as XX% or 0.XX

        If this param is True: 0.XX
        If this param is False: XX%

    '''
    params = (
        ('percabs', True),  # Original CommissionInfo took 0.xx for percentages
    )
