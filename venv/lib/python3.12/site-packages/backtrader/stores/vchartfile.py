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

import os.path

import backtrader as bt


class VChartFile(bt.Store):
    '''Store provider for Visual Chart binary files

    Params:

      - ``path`` (default:``None``):

        If the path is ``None`` and running under *Windows*, the registry will
        be examined to find the root directory of the *Visual Chart* files.
    '''

    params = (
        ('path', None),
    )

    def __init__(self):
        self._path = self.p.path
        if self._path is None:
            self._path = self._find_vchart()

    @staticmethod
    def _find_vchart():
        # Find VisualChart registry key to get data directory
        # If not found returns ''
        VC_KEYNAME = r'SOFTWARE\VCG\Visual Chart 6\Config'
        VC_KEYVAL = 'DocsDirectory'
        VC_DATADIR = ['Realserver', 'Data', '01']

        VC_NONE = ''

        from backtrader.utils.py3 import winreg
        if winreg is None:
            return VC_NONE

        vcdir = None
        # Search for Directory in the usual root keys
        for rkey in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE,):
            try:
                vckey = winreg.OpenKey(rkey, VC_KEYNAME)
            except WindowsError as e:
                continue

            # Try to get the key value
            try:
                vcdir, _ = winreg.QueryValueEx(vckey, VC_KEYVAL)
            except WindowsError as e:
                continue
            else:
                break  # found vcdir

        if vcdir is not None:  # something was found
            vcdir = os.path.join(vcdir, *VC_DATADIR)
        else:
            vcdir = VC_NONE

        return vcdir

    def get_datapath(self):
        return self._path
