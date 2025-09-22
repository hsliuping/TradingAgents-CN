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

from backtrader import date2num
import backtrader.feed as feed


class BlazeData(feed.DataBase):
    '''
    Support for `Blaze <blaze.pydata.org>`_ ``Data`` objects.

    Only numeric indices to columns are supported.

    Note:

      - The ``dataname`` parameter is a blaze ``Data`` object

      - A negative value in any of the parameters for the Data lines
        indicates it's not present in the DataFrame
        it is
    '''

    params = (
        # datetime must be present
        ('datetime', 0),
        # pass -1 for any of the following to indicate absence
        ('open', 1),
        ('high', 2),
        ('low', 3),
        ('close', 4),
        ('volume', 5),
        ('openinterest', 6),
    )

    datafields = [
        'datetime', 'open', 'high', 'low', 'close', 'volume', 'openinterest'
    ]

    def start(self):
        super(BlazeData, self).start()

        # reset the iterator on each start
        self._rows = iter(self.p.dataname)

    def _load(self):
        try:
            row = next(self._rows)
        except StopIteration:
            return False

        # Set the standard datafields - except for datetime
        for datafield in self.datafields[1:]:
            # get the column index
            colidx = getattr(self.params, datafield)

            if colidx < 0:
                # column not present -- skip
                continue

            # get the line to be set
            line = getattr(self.lines, datafield)
            line[0] = row[colidx]

        # datetime - assumed blaze always serves a native datetime.datetime
        colidx = getattr(self.params, self.datafields[0])
        dt = row[colidx]
        dtnum = date2num(dt)

        # get the line to be set
        line = getattr(self.lines, self.datafields[0])
        line[0] = dtnum

        # Done ... return
        return True
