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

import sys

from . import Indicator, MovingAverage


class EnvelopeMixIn(object):
    '''
    MixIn class to create a subclass with another indicator. The main line of
    that indicator will be surrounded by an upper and lower band separated a
    given "perc"entage from the input main line

    The usage is:

      - Class XXXEnvelope(XXX, EnvelopeMixIn)

    Formula:
      - 'line' (inherited from XXX))
      - top = 'line' * (1 + perc)
      - bot = 'line' * (1 - perc)

    See also:
      - http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:moving_average_envelopes
    '''
    lines = ('top', 'bot',)
    params = (('perc', 2.5),)
    plotlines = dict(top=dict(_samecolor=True), bot=dict(_samecolor=True),)

    def __init__(self):
        # Mix-in & directly from object -> does not necessarily need super
        # super(EnvelopeMixIn, self).__init__()
        perc = self.p.perc / 100.0

        self.lines.top = self.lines[0] * (1.0 + perc)
        self.lines.bot = self.lines[0] * (1.0 - perc)

        super(EnvelopeMixIn, self).__init__()


class _EnvelopeBase(Indicator):
    lines = ('src',)

    # plot the envelope lines along the passed source
    plotinfo = dict(subplot=False)

    # Do not replot the data line
    plotlines = dict(src=dict(_plotskip=True))

    def __init__(self):
        self.lines.src = self.data
        super(_EnvelopeBase, self).__init__()


class Envelope(_EnvelopeBase, EnvelopeMixIn):
    '''
    It creates envelopes bands separated from the source data by a given
    percentage

    Formula:
      - src = datasource
      - top = src * (1 + perc)
      - bot = src * (1 - perc)

    See also:
      - http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:moving_average_envelopes
    '''


# Automatic creation of Moving Average Envelope classes

for movav in MovingAverage._movavs[1:]:
    _newclsdoc = '''
    %s and envelope bands separated "perc" from it

    Formula:
      - %s (from %s)
      - top = %s * (1 + perc)
      - bot = %s * (1 - perc)

    See also:
      - http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:moving_average_envelopes
    '''
    # Skip aliases - they will be created automatically
    if getattr(movav, 'aliased', ''):
        continue

    movname = movav.__name__
    linename = movav.lines._getlinealias(0)
    newclsname = movname + 'Envelope'

    newaliases = []
    for alias in getattr(movav, 'alias', []):
        for suffix in ['Envelope']:
            newaliases.append(alias + suffix)

    newclsdoc = _newclsdoc % (movname, linename, movname, linename, linename)

    newclsdct = {'__doc__': newclsdoc,
                 '__module__': EnvelopeMixIn.__module__,
                 '_notregister': True,
                 'alias': newaliases}
    newcls = type(str(newclsname), (movav, EnvelopeMixIn), newclsdct)
    module = sys.modules[EnvelopeMixIn.__module__]
    setattr(module, newclsname, newcls)
