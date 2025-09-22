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

import math


def average(x, bessel=False):
    '''
    Args:
      x: iterable with len

      oneless: (default ``False``) reduces the length of the array for the
                division.

    Returns:
      A float with the average of the elements of x
    '''
    return math.fsum(x) / (len(x) - bessel)


def variance(x, avgx=None):
    '''
    Args:
      x: iterable with len

    Returns:
      A list with the variance for each element of x
    '''
    if avgx is None:
        avgx = average(x)
    return [pow(y - avgx, 2.0) for y in x]


def standarddev(x, avgx=None, bessel=False):
    '''
    Args:
      x: iterable with len

      bessel: (default ``False``) to be passed to the average to divide by
      ``N - 1`` (Bessel's correction)

    Returns:
      A float with the standard deviation of the elements of x
    '''
    return math.sqrt(average(variance(x, avgx), bessel=bessel))
