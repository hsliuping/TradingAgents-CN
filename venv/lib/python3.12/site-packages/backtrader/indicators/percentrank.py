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

from math import fsum

from . import BaseApplyN


__all__ = ['PercentRank', 'PctRank']


class PercentRank(BaseApplyN):
    '''
    Measures the percent rank of the current value with respect to that of
    period bars ago
    '''
    alias = ('PctRank',)
    lines = ('pctrank',)
    params = (
        ('period', 50),
        ('func', lambda d: fsum(x < d[-1] for x in d) / len(d)),
    )
