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

from ..comminfo import CommInfoBase


class CommInfo(CommInfoBase):
    pass  # clone of CommissionInfo but with xx% instead of 0.xx


class CommInfo_Futures(CommInfoBase):
    params = (
        ('stocklike', False),
    )


class CommInfo_Futures_Perc(CommInfo_Futures):
    params = (
        ('commtype', CommInfoBase.COMM_PERC),
    )


class CommInfo_Futures_Fixed(CommInfo_Futures):
    params = (
        ('commtype', CommInfoBase.COMM_FIXED),
    )


class CommInfo_Stocks(CommInfoBase):
    params = (
        ('stocklike', True),
    )


class CommInfo_Stocks_Perc(CommInfo_Stocks):
    params = (
        ('commtype', CommInfoBase.COMM_PERC),
    )


class CommInfo_Stocks_Fixed(CommInfo_Stocks):
    params = (
        ('commtype', CommInfoBase.COMM_FIXED),
    )
