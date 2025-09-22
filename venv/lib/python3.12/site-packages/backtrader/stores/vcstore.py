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
from datetime import date, datetime, time, timedelta
import os.path
import threading
import time as _timemod

import ctypes

from backtrader import TimeFrame, Position
from backtrader.feed import DataBase
from backtrader.metabase import MetaParams
from backtrader.utils.py3 import (MAXINT, range, queue, string_types,
                                  with_metaclass)
from backtrader.utils import AutoDict


class _SymInfo(object):
    # Replica of the SymbolInfo COM object to pass it over thread boundaries
    _fields = ['Type', 'Description', 'Decimals', 'TimeOffset',
               'PointValue', 'MinMovement']

    def __init__(self, syminfo):
        for f in self._fields:
            setattr(self, f, getattr(syminfo, f))

# This type is used inside 'PumpEvents', but if we create the type
# afresh each time 'PumpEvents' is called we end up creating cyclic
# garbage for each call.  So we define it here instead.
_handles_type = ctypes.c_void_p * 1


def PumpEvents(timeout=-1, hevt=None, cb=None):
    """This following code waits for 'timeout' seconds in the way
    required for COM, internally doing the correct things depending
    on the COM appartment of the current thread.  It is possible to
    terminate the message loop by pressing CTRL+C, which will raise
    a KeyboardInterrupt.
    """
    # XXX Should there be a way to pass additional event handles which
    # can terminate this function?

    # XXX XXX XXX
    #
    # It may be that I misunderstood the CoWaitForMultipleHandles
    # function.  Is a message loop required in a STA?  Seems so...
    #
    # MSDN says:
    #
    # If the caller resides in a single-thread apartment,
    # CoWaitForMultipleHandles enters the COM modal loop, and the
    # thread's message loop will continue to dispatch messages using
    # the thread's message filter. If no message filter is registered
    # for the thread, the default COM message processing is used.
    #
    # If the calling thread resides in a multithread apartment (MTA),
    # CoWaitForMultipleHandles calls the Win32 function
    # MsgWaitForMultipleObjects.

    # Timeout expected as float in seconds - *1000 to miliseconds
    # timeout = -1 -> INFINITE 0xFFFFFFFF;
    # It can also be a callable which should return an amount in seconds

    if hevt is None:
        hevt = ctypes.windll.kernel32.CreateEventA(None, True, False, None)

    handles = _handles_type(hevt)
    RPC_S_CALLPENDING = -2147417835

    # @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
    def HandlerRoutine(dwCtrlType):
        if dwCtrlType == 0:  # CTRL+C
            ctypes.windll.kernel32.SetEvent(hevt)
            return 1
        return 0

    HandlerRoutine = (
        ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)(HandlerRoutine)
    )

    ctypes.windll.kernel32.SetConsoleCtrlHandler(HandlerRoutine, 1)
    while True:
        try:
            tmout = timeout()  # check if it's a callable
        except TypeError:
            tmout = timeout  # it seems to be a number

        if tmout > 0:
            tmout *= 1000
        tmout = int(tmout)

        try:
            res = ctypes.oledll.ole32.CoWaitForMultipleHandles(
                0,  # COWAIT_FLAGS
                int(tmout),  # dwtimeout
                len(handles),  # number of handles in handles
                handles,  # handles array
                # pointer to indicate which handle was signaled
                ctypes.byref(ctypes.c_ulong())
            )

        except WindowsError as details:
            if details.args[0] == RPC_S_CALLPENDING:  # timeout expired
                if cb is not None:
                    cb()

                continue

            else:
                ctypes.windll.kernel32.CloseHandle(hevt)
                ctypes.windll.kernel32.SetConsoleCtrlHandler(HandlerRoutine, 0)
                raise  # something else happened
        else:
            ctypes.windll.kernel32.CloseHandle(hevt)
            ctypes.windll.kernel32.SetConsoleCtrlHandler(HandlerRoutine, 0)
            raise KeyboardInterrupt

        # finally:
        # if False:
            # ctypes.windll.kernel32.CloseHandle(hevt)
            # ctypes.windll.kernel32.SetConsoleCtrlHandler(HandlerRoutine, 0)
            # break


class RTEventSink(object):
    def __init__(self, store):
        self.store = store
        self.vcrtmod = store.vcrtmod
        self.lastconn = None

    def OnNewTicks(self, ArrayTicks):
        pass

    def OnServerShutDown(self):
        self.store._vcrt_connection(self.store._RT_SHUTDOWN)

    def OnInternalEvent(self, p1, p2, p3):
        if p1 != 1:  # Apparently "Connection Event"
            return

        if p2 == self.lastconn:
            return  # do not notify twice

        self.lastconn = p2  # keep new notification code

        # p2 should be 0 (disconn), 1 (conn)
        self.store._vcrt_connection(self.store._RT_BASEMSG - p2)


class MetaSingleton(MetaParams):
    '''Metaclass to make a metaclassed class a singleton'''
    def __init__(cls, name, bases, dct):
        super(MetaSingleton, cls).__init__(name, bases, dct)
        cls._singleton = None

    def __call__(cls, *args, **kwargs):
        if cls._singleton is None:
            cls._singleton = (
                super(MetaSingleton, cls).__call__(*args, **kwargs))

        return cls._singleton


class VCStore(with_metaclass(MetaSingleton, object)):
    '''Singleton class wrapping an ibpy ibConnection instance.

    The parameters can also be specified in the classes which use this store,
    like ``VCData`` and ``VCBroker``

    '''
    BrokerCls = None  # broker class will autoregister
    DataCls = None  # data class will auto register

    # 32 bit max unsigned int for openinterest correction
    MAXUINT = 0xffffffff // 2

    # to remove at least 1 sec or else there seem to be internal conv problems
    MAXDATE1 = datetime.max - timedelta(days=1, seconds=1)
    MAXDATE2 = datetime.max - timedelta(seconds=1)

    _RT_SHUTDOWN = -0xffff
    _RT_BASEMSG = -0xfff0
    _RT_DISCONNECTED = -0xfff0
    _RT_CONNECTED = -0xfff1
    _RT_LIVE = -0xfff2
    _RT_DELAYED = -0xfff3
    _RT_TYPELIB = -0xffe0
    _RT_TYPEOBJ = -0xffe1
    _RT_COMTYPES = -0xffe2

    @classmethod
    def getdata(cls, *args, **kwargs):
        '''Returns ``DataCls`` with args, kwargs'''
        return cls.DataCls(*args, **kwargs)

    @classmethod
    def getbroker(cls, *args, **kwargs):
        '''Returns broker with *args, **kwargs from registered ``BrokerCls``'''
        return cls.BrokerCls(*args, **kwargs)

    # DLLs to parse if found for TypeLibs
    VC64_DLLS = ('VCDataSource64.dll', 'VCRealTimeLib64.dll',
                 'COMTraderInterfaces64.dll',)

    VC_DLLS = ('VCDataSource.dll', 'VCRealTimeLib.dll',
               'COMTraderInterfaces.dll',)

    # Well known CLSDI
    VC_TLIBS = (
        ['{EB2A77DC-A317-4160-8833-DECF16275A05}', 1, 0],  # vcdatasource64
        ['{86F1DB04-2591-4866-A361-BB053D77FA18}', 1, 0],  # vcrealtime64
        ['{20F8873C-35BE-4DB4-8C2A-0A8D40F8AEC3}', 1, 0],  # raderinterface64
    )

    VC_KEYNAME = r'SOFTWARE\VCG\Visual Chart 6\Config'
    VC_KEYVAL = 'Directory'
    VC_BINPATH = 'bin'

    def find_vchart(self):
        # Tries to locate VisualChart in the registry to get the installation
        # directory
        # If not found returns well-known typelibs clsid
        # Else it will scan the directory to locate the 64/32 bit dlls and
        # return the paths
        import _winreg  # keep import local to avoid breaking test cases

        vcdir = None

        # Search for Directory in the usual root keys
        for rkey in (_winreg.HKEY_CURRENT_USER, _winreg.HKEY_LOCAL_MACHINE,):
            try:
                vckey = _winreg.OpenKey(rkey, self.VC_KEYNAME)
            except WindowsError as e:
                continue

            # Try to get the key value
            try:
                vcdir, _ = _winreg.QueryValueEx(vckey, self.VC_KEYVAL)
            except WindowsError as e:
                continue
            else:
                break  # found vcdir

        if vcdir is None:
            return self.VC_TLIBS  # no dir found, last resort

        # DLLs are in the bin directory
        vcbin = os.path.join(vcdir, self.VC_BINPATH)

        # Search for the 3 libraries (64/32 bits) in the found dir
        for dlls in (self.VC64_DLLS, self.VC_DLLS,):
            dfound = []
            for dll in dlls:
                fpath = os.path.join(vcbin, dll)
                if not os.path.isfile(fpath):
                    break
                dfound.append(fpath)

            if len(dfound) == len(dlls):
                return dfound

        # not all dlls were found, last resort
        return self.VC_TLIBS

    def _load_comtypes(self):
        # Keep comtypes imports local to avoid breaking testcases
        try:
            import comtypes
            self.comtypes = comtypes

            from comtypes.client import CreateObject, GetEvents, GetModule
            self.CreateObject = CreateObject
            self.GetEvents = GetEvents
            self.GetModule = GetModule
        except ImportError:
            return False

        return True  # notifiy comtypes was loaded

    def __init__(self):
        self._connected = False  # modules/objects created

        self.notifs = collections.deque()  # hold notifications to deliver

        self.t_vcconn = None  # control connection status

        # hold deques to market data symbols
        self._dqs = collections.deque()
        self._qdatas = dict()
        self._tftable = dict()

        if not self._load_comtypes():
            txt = 'Failed to import comtypes'
            msg = self._RT_COMTYPES, txt
            self.put_notification(msg, *msg)
            return

        vctypelibs = self.find_vchart()
        # Try to load the modules
        try:
            self.vcdsmod = self.GetModule(vctypelibs[0])
            self.vcrtmod = self.GetModule(vctypelibs[1])
            self.vcctmod = self.GetModule(vctypelibs[2])
        except WindowsError as e:
            self.vcdsmod = None
            self.vcrtmod = None
            self.vcctmod = None
            txt = 'Failed to Load COM TypeLib Modules {}'.format(e)
            msg = self._RT_TYPELIB, txt
            self.put_notification(msg, *msg)
            return

        # Try to load the main objects
        try:
            self.vcds = self.CreateObject(self.vcdsmod.DataSourceManager)
            # self.vcrt = self.CreateObject(self.vcrtmod.RealTime)
            self.vcct = self.CreateObject(self.vcctmod.Trader)
        except WindowsError as e:
            txt = ('Failed to Load COM TypeLib Objects but the COM TypeLibs '
                   'have been loaded. If VisualChart has been recently '
                   'installed/updated, restarting Windows may be necessary '
                   'to register the Objects: {}'.format(e))
            msg = self._RT_TYPELIB, txt
            self.put_notification(msg, *msg)
            self.vcds = None
            self.vcrt = None
            self.vcct = None
            return

        self._connected = True

        # Build a table of VCRT Field_XX mappings for debugging purposes
        self.vcrtfields = dict()
        for name in dir(self.vcrtmod):
            if name.startswith('Field'):
                self.vcrtfields[getattr(self.vcrtmod, name)] = name

        # Modules and objects can be created
        self._tftable = {
            TimeFrame.Ticks: (self.vcdsmod.CT_Ticks, 1),
            TimeFrame.MicroSeconds: (self.vcdsmod.CT_Ticks, 1),  # To Resample
            TimeFrame.Seconds: (self.vcdsmod.CT_Ticks, 1),  # To Resample
            TimeFrame.Minutes: (self.vcdsmod.CT_Minutes, 1),
            TimeFrame.Days: (self.vcdsmod.CT_Days, 1),
            TimeFrame.Weeks: (self.vcdsmod.CT_Weeks, 1),
            TimeFrame.Months: (self.vcdsmod.CT_Months, 1),
            TimeFrame.Years: (self.vcdsmod.CT_Months, 12),
        }

    def put_notification(self, msg, *args, **kwargs):
        self.notifs.append((msg, args, kwargs))

    def get_notifications(self):
        '''Return the pending "store" notifications'''
        self.notifs.append(None)  # Mark current end of notifs
        return [x for x in iter(self.notifs.popleft, None)]  # popleft til None

    def start(self, data=None, broker=None):
        if not self._connected:
            return

        if self.t_vcconn is None:
            # Kickstart connection thread check
            self.t_vcconn = t = threading.Thread(target=self._start_vcrt)
            t.daemon = True  # Do not stop a general exit
            t.start()

        if broker is not None:
            t = threading.Thread(target=self._t_broker, args=(broker,))
            t.daemon = True
            t.start()

    def stop(self):
        pass  # nothing to do

    def connected(self):
        return self._connected

    def _start_vcrt(self):
        # Use VCRealTime to monitor the connection status
        self.comtypes.CoInitialize()  # running in another thread
        vcrt = self.CreateObject(self.vcrtmod.RealTime)
        sink = RTEventSink(self)
        conn = self.GetEvents(vcrt, sink)
        PumpEvents()
        self.comtypes.CoUninitialize()

    def _vcrt_connection(self, status):
        if status == -0xffff:
            txt = 'VisualChart shutting down',
        # p2: 0 -> Disconnected /  p2: 1 -> Reconnected
        elif status == -0xfff0:
            txt = 'VisualChart is Disconnected'
        elif status == -0xfff1:
            txt = 'VisualChart is Connected'
        else:
            txt = 'VisualChart unknown connection status '

        msg = txt, status
        self.put_notification(msg, *msg)

        for q in self._dqs:
            q.put(status)

    def _tf2ct(self, timeframe, compression):
        # Translates timeframes to known compression types in VisualChart
        timeframe, extracomp = self._tftable[timeframe]
        return timeframe, compression * extracomp

    def _ticking(self, timeframe):
        # Translates timeframes to known compression types in VisualChart
        vctimeframe, _ = self._tftable[timeframe]
        return vctimeframe == self.vcdsmod.CT_Ticks

    def _getq(self, data):
        q = queue.Queue()
        self._dqs.append(q)
        self._qdatas[q] = data
        return q

    def _delq(self, q):
        self._dqs.remove(q)
        self._qdatas.pop(q)

    def _rtdata(self, data, symbol):
        kwargs = dict(data=data, symbol=symbol)
        t = threading.Thread(target=self._t_rtdata, kwargs=kwargs)
        t.daemon = True
        t.start()

    # Broker functions
    def _t_rtdata(self, data, symbol):
        self.comtypes.CoInitialize()  # running in another thread
        vcrt = self.CreateObject(self.vcrtmod.RealTime)
        conn = self.GetEvents(vcrt, data)
        data._vcrt = vcrt
        vcrt.RequestSymbolFeed(symbol, False)  # no limits
        PumpEvents()
        del conn  # ensure events go away
        self.comtypes.CoUninitialize()

    def _symboldata(self, symbol):

        # Assumption -> we are connected and the symbol has been found
        self.vcds.ActiveEvents = 0
        # self.vcds.EventsType = self.vcdsmod.EF_Always

        serie = self.vcds.NewDataSerie(symbol,
                                       self.vcdsmod.CT_Days, 1,
                                       self.MAXDATE1, self.MAXDATE2)

        syminfo = _SymInfo(serie.GetSymbolInfo())
        self.vcds.DeleteDataSource(serie)
        return syminfo

    def _canceldirectdata(self, q):
        self._delq(q)

    def _directdata(self, data,
                    symbol, timeframe, compression, d1, d2=None,
                    historical=False):

        # Assume the data has checked the existence of the symbol
        timeframe, compression = self._tf2ct(timeframe, compression)
        kwargs = locals().copy()  # make a copy of the args
        kwargs.pop('self')
        kwargs['q'] = q = self._getq(data)

        t = threading.Thread(target=self._t_directdata, kwargs=kwargs)
        t.daemon = True
        t.start()

        # use the queue to synchronize until symbolinfo has been gotten
        return q  # tell the caller where to expect the hist data

    def _t_directdata(self, data,
                      symbol, timeframe, compression, d1, d2, q,
                      historical):

        self.comtypes.CoInitialize()  # start com threading
        vcds = self.CreateObject(self.vcdsmod.DataSourceManager)

        historical = historical or d2 is not None
        if not historical:
            vcds.ActiveEvents = 1
            vcds.EventsType = self.vcdsmod.EF_Always
        else:
            vcds.ActiveEvents = 0

        if d2 is not None:
            serie = vcds.NewDataSerie(symbol, timeframe, compression, d1, d2)
        else:
            serie = vcds.NewDataSerie(symbol, timeframe, compression, d1)

        data._setserie(serie)

        # processing of bars can continue
        data.OnNewDataSerieBar(serie, forcepush=historical)
        if historical:  # push the last bar
            q.put(None)        # Signal end of transmission
            dsconn = None
        else:
            dsconn = self.GetEvents(vcds, data)  # finally connect the events
            pass

        # pump events in this thread - call ping
        PumpEvents(timeout=data._getpingtmout, cb=data.ping)
        if dsconn is not None:
            del dsconn  # Docs recommend deleting the connection

        # Delete the series before coming out of the thread
        vcds.DeleteDataSource(serie)
        self.comtypes.CoUninitialize()  # Terminate com threading

    # Broker functions
    def _t_broker(self, broker):
        self.comtypes.CoInitialize()  # running in another thread
        trader = self.CreateObject(self.vcctmod.Trader)
        conn = self.GetEvents(trader, broker(trader))
        PumpEvents()
        del conn  # ensure events go away
        self.comtypes.CoUninitialize()
