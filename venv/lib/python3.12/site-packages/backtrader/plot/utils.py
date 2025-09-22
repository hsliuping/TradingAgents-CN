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

from colorsys import rgb_to_hls as rgb2hls, hls_to_rgb as hls2rgb

import matplotlib.colors as mplcolors
import matplotlib.path as mplpath


def tag_box_style(x0, y0, width, height, mutation_size, mutation_aspect=1):
    """
    Given the location and size of the box, return the path of
    the box around it.

     - *x0*, *y0*, *width*, *height* : location and size of the box
     - *mutation_size* : a reference scale for the mutation.
     - *aspect_ratio* : aspect-ration for the mutation.
    """

    # note that we are ignoring mutation_aspect. This is okay in general.
    mypad = 0.2
    pad = mutation_size * mypad

    # width and height with padding added.
    width, height = width + 2.*pad, height + 2.*pad,

    # boundary of the padded box
    x0, y0 = x0-pad, y0-pad,
    x1, y1 = x0+width, y0 + height

    cp = [(x0, y0),
          (x1, y0), (x1, y1), (x0, y1),
          (x0-pad, (y0+y1)/2.), (x0, y0),
          (x0, y0)]

    com = [mplpath.Path.MOVETO,
           mplpath.Path.LINETO, mplpath.Path.LINETO, mplpath.Path.LINETO,
           mplpath.Path.LINETO, mplpath.Path.LINETO,
           mplpath.Path.CLOSEPOLY]

    path = mplpath.Path(cp, com)

    return path


def shade_color(color, percent):
    """Shade Color
    This color utility function allows the user to easily darken or
    lighten a color for plotting purposes.
    Parameters
    ----------
    color : string, list, hexvalue
        Any acceptable Matplotlib color value, such as
        'red', 'slategrey', '#FFEE11', (1,0,0)
    percent :  the amount by which to brighten or darken the color.
    Returns
    -------
    color : tuple of floats
        tuple representing converted rgb values
    """

    rgb = mplcolors.colorConverter.to_rgb(color)

    h, l, s = rgb2hls(*rgb)

    l *= 1 + float(percent)/100

    l = min(1, l)
    l = max(0, l)

    r, g, b = hls2rgb(h, l, s)

    return r, g, b
