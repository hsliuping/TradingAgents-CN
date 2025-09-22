# coding=utf-8
# Copyright (c) 2016, Cedric Zhuang
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of disclaimer nor the names of its contributors may
#       be used to endorse or promote products derived from this software
#       without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE REGENTS AND CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import unicode_literals

import functools
import itertools
import re
from typing import Optional, Callable, Union

import numpy as np
import pandas as pd

__author__ = 'Cedric Zhuang'

from numpy.lib.stride_tricks import as_strided


class StockStatsError(Exception):
    pass


_dft_windows = {
    # sort alphabetically
    'ao': (5, 34),
    'aroon': 25,
    'atr': 14,
    'boll': 20,
    'cci': 14,
    'change': 1,
    'chop': 14,
    'cmo': 14,
    'coppock': (10, 11, 14),
    'cr': 26,
    'cti': 12,
    'dma': (10, 50),
    'eri': 13,
    'eribear': 13,
    'eribull': 13,
    'ichimoku': (9, 26, 52),
    'inertia': (20, 14),
    'ftr': 9,
    'kama': (10, 5, 34),  # window, fast, slow
    'kdjd': 9,
    'kdjj': 9,
    'kdjk': 9,
    'ker': 10,
    'macd': (12, 26, 9),  # short, long, signal
    'mfi': 14,
    'ndi': 14,
    'pdi': 14,
    'pgo': 14,
    'ppo': (12, 26, 9),  # short, long, signal
    'pvo': (12, 26, 9),  # short, long, signal
    'psl': 12,
    'qqe': (14, 5),  # rsi, rsi ema
    'rsi': 14,
    'rsv': 9,
    'rvgi': 14,
    'stochrsi': 14,
    'supertrend': 14,
    'tema': 5,
    'trix': 12,
    'wr': 14,
    'wt': (10, 21),
    'vr': 26,
    'vwma': 14,
    'num': 0,
}


def set_dft_window(name: str, windows: Union[int, tuple[int, ...]]):
    ret = _dft_windows.get(name)
    _dft_windows[name] = windows
    return ret


_dft_column = {
    # sort alphabetically
    'cti': 'close',
    'dma': 'close',
    'kama': 'close',
    'ker': 'close',
    'psl': 'close',
    'tema': 'close',
    'trix': 'close',
}


def dft_windows(name: str) -> Optional[str]:
    if name not in _dft_windows:
        return None
    dft = _dft_windows[name]
    if isinstance(dft, int):
        return str(dft)
    return ','.join(map(str, dft))


def dft_column(name: str) -> Optional[str]:
    if name not in _dft_column:
        return None
    return _dft_column[name]


class _Meta:
    def __init__(self,
                 name,
                 *,
                 column=None,
                 windows=None):
        self._name = name
        self._column = column
        self._windows = windows
        self._dft_column = dft_column(name)
        self._dft_windows = dft_windows(name)

    @staticmethod
    def _process_segment(windows):
        if '~' in windows:
            start, end = windows.split('~')
            shifts = range(int(start), int(end) + 1)
        else:
            shifts = [int(windows)]
        return shifts

    @property
    def ints(self) -> list[int]:
        items = map(self._process_segment, self.windows.split(','))
        return list(itertools.chain(*items))

    @property
    def int(self) -> int:
        numbers = self.ints
        if len(numbers) != 1:
            raise StockStatsError('only accept 1 number')
        return numbers[0]

    def _get_int(self, i):
        numbers = self.ints
        if len(numbers) < i + 1:
            # try the defaults
            dft_numbers = _dft_windows[self._name]
            if len(dft_numbers) > i:
                return dft_numbers[i]
            raise StockStatsError(f'not enough ints, need {i + 1}')
        return self.ints[i]

    @property
    def int0(self) -> int:
        return self._get_int(0)

    @property
    def int1(self) -> int:
        return self._get_int(1)

    @property
    def int2(self) -> int:
        return self._get_int(2)

    @property
    def positive_int(self) -> int:
        ret = self.int
        if ret <= 0:
            raise StockStatsError('window must be greater than 0')
        return ret

    @property
    def windows(self):
        if self._windows is None:
            return self._dft_windows
        return self._windows

    @property
    def column(self):
        if self._column is None:
            return self._dft_column
        return self._column

    @property
    def name(self):
        if self._windows is None and self._column is None:
            return self._name
        if self._column is None:
            return f'{self._name}_{self._windows}'
        return f'{self.column}_{self.windows}_{self._name}'

    def set_name(self, name: str):
        self._name = name
        return self

    def name_ex(self, ex):
        ret = f'{self._name}{ex}'
        if self._windows is None:
            return ret
        return f'{ret}_{self.windows}'


def _call_handler(handler: Callable):
    meta = _Meta(handler.__name__[5:])
    return handler(meta)


def wrap(df, index_column=None):
    """ wraps a pandas DataFrame to StockDataFrame

    :param df: pandas DataFrame
    :param index_column: the name of the index column, default to ``date``
    :return: an object of StockDataFrame
    """
    return StockDataFrame.retype(df, index_column)


def unwrap(sdf):
    """ convert a StockDataFrame back to a pandas DataFrame """
    return pd.DataFrame(sdf)


class StockDataFrame(pd.DataFrame):
    # Start of options.
    KDJ_PARAM = (2.0 / 3.0, 1.0 / 3.0)

    BOLL_STD_TIMES = 2

    DX_SMMA = 14
    ADX_EMA = 6
    ADXR_EMA = 6

    CR_MA = (5, 10, 20)

    SUPERTREND_MUL = 3

    # End of options

    @staticmethod
    def _df_to_series(column):
        # if column is data frame, retrieve the first column
        if isinstance(column, pd.DataFrame):
            column = column.iloc[:, 0]
        return column

    @property
    def high(self) -> pd.Series:
        return self._df_to_series(self['high'])

    @property
    def low(self) -> pd.Series:
        return self._df_to_series(self['low'])

    @property
    def close(self) -> pd.Series:
        return self._df_to_series(self['close'])

    @property
    def open(self) -> pd.Series:
        return self._df_to_series(self['open'])

    @property
    def volume(self) -> pd.Series:
        return self._df_to_series(self['volume'])

    @property
    def amount(self) -> pd.Series:
        return self._df_to_series(self['amount'])

    def _get_change(self, meta: _Meta):
        """ Get the percentage change column

        It's an alias for ROC

        :return: result series
        """
        self[meta.name] = self.roc(self.close, meta.int)

    def _get_p(self, meta: _Meta):
        """ get the permutation of specified range

        example:
        index    x   x_-2,-1_p
        0        1         NaN
        1       -1         NaN
        2        3           2  (0.x > 0, and assigned to weight 2)
        3        5           1  (2.x > 0, and assigned to weight 1)
        4        1           3
        """
        # initialize the column if not
        _ = self.get(meta.column)
        shifts = meta.ints[::-1]
        indices: Optional[pd.Series] = None
        count = 0
        for shift in shifts:
            shifted = self.shift(-shift)
            index = (shifted[meta.column] > 0) * (2 ** count)
            if indices is None:
                indices = index
            else:
                indices += index
            count += 1
        if indices is not None:
            cp = indices.copy()
            self.set_nan(cp, shifts)
            self[meta.name] = cp

    @classmethod
    def to_ints(cls, shifts):
        items = map(cls._process_shifts_segment, shifts.split(','))
        return sorted(list(set(itertools.chain(*items))))

    @classmethod
    def to_int(cls, shifts):
        numbers = cls.to_ints(shifts)
        if len(numbers) != 1:
            raise IndexError("only accept 1 number.")
        return numbers[0]

    @staticmethod
    def _process_shifts_segment(shift_segment):
        if '~' in shift_segment:
            start, end = shift_segment.split('~')
            shifts = range(int(start), int(end) + 1)
        else:
            shifts = [int(shift_segment)]
        return shifts

    @classmethod
    def set_nan(cls, pd_obj, shift):
        try:
            iter(shift)
            max_shift = max(shift)
            min_shift = min(shift)
            cls._set_nan_of_single_shift(pd_obj, max_shift)
            cls._set_nan_of_single_shift(pd_obj, min_shift)
        except TypeError:
            # shift is not iterable
            cls._set_nan_of_single_shift(pd_obj, shift)

    @staticmethod
    def _set_nan_of_single_shift(pd_obj, shift):
        val = np.nan
        if shift > 0:
            pd_obj.iloc[-shift:] = val
        elif shift < 0:
            pd_obj.iloc[:-shift] = val

    def _get_r(self, meta: _Meta):
        """ Get rate of change of column

        Note this function is different to the roc function.
        negative values meaning data in the past,
        positive values meaning data in the future.
        """
        shift = -meta.int
        self[meta.name] = self.roc(self[meta.column], shift)

    @staticmethod
    def s_shift(series: pd.Series, window: int):
        """ Shift the series

        When window is negative, shift the past period to current.
        Fill the gap with the first data available.

        When window is positive, shift the future period to current.
        Fill the gap with last data available.

        :param series: the series to shift
        :param window: number of periods to shift
        :return: the shifted series with filled gap
        """
        if series.empty:
            return series.copy()
        ret = series.shift(-window).copy()
        if window < 0:
            ret.iloc[:-window] = series.iloc[0]
        elif window > 0:
            ret.iloc[-window:] = series.iloc[-1]
        return ret

    def _get_s(self, meta: _Meta):
        """ Get the column shifted by periods

        Note this method is different to the shift method of pandas.
        negative values meaning data in the past,
        positive values meaning data in the future.
        """
        self[meta.name] = self.s_shift(self[meta.column], meta.int)

    def _get_log_ret(self, _: _Meta):
        close = self.close
        self['log-ret'] = np.log(close / self.s_shift(close, -1))

    def _get_c(self, meta: _Meta) -> pd.Series:
        """ get the count of column in range (shifts)

        example: change_20_c
        :return: result series
        """
        rolled = self._rolling(self[meta.column], meta.int)
        counts = rolled.apply(np.count_nonzero, raw=True)
        self[meta.name] = counts
        return counts

    def _get_fc(self, meta: _Meta) -> pd.Series:
        """ get the count of column in range of future (shifts)

        example: change_20_fc
        :return: result series
        """
        shift = meta.int
        series = self[meta.column]
        reversed_series = series[::-1]
        rolled = self._rolling(reversed_series, shift)
        reversed_counts = rolled.apply(np.count_nonzero, raw=True)
        counts = reversed_counts[::-1]
        self[meta.name] = counts
        return counts

    def _shifted_columns(self,
                         column: pd.Series,
                         shifts: list[int]) -> pd.DataFrame:
        # initialize the column if not
        col = self.get(column)
        res = pd.DataFrame()
        for i in shifts:
            res[int(i)] = self.s_shift(col, i).values
        return res

    def _get_max(self, meta: _Meta):
        column = meta.column
        shifts = meta.ints
        cols = self._shifted_columns(column, shifts)
        self[meta.name] = cols.max(axis=1).values

    def _get_min(self, meta: _Meta):
        column = meta.column
        shifts = meta.ints
        cols = self._shifted_columns(column, shifts)
        self[meta.name] = cols.min(axis=1).values

    def _rsv(self, window):
        low_min = self.mov_min(self.low, window)
        high_max = self.mov_max(self.high, window)

        cv = (self.close - low_min) / (high_max - low_min)
        cv.fillna(0.0, inplace=True)
        return cv * 100

    def _get_rsv(self, meta: _Meta):
        """ Calculate the RSV (Raw Stochastic Value) within N periods

        This value is essential for calculating KDJs
        Current day is included in N

        """
        self[meta.name] = self._rsv(meta.int)

    def _rsi(self, window) -> pd.Series:
        change = self.close.diff()
        change.iloc[0] = 0
        close_pm = (change + change.abs()) / 2
        close_nm = (-change + change.abs()) / 2
        p_ema = self.smma(close_pm, window)
        n_ema = self.smma(close_nm, window)

        rs = p_ema / n_ema
        return 100 - 100 / (1.0 + rs)

    def _get_rsi(self, meta: _Meta):
        """ Calculate the RSI (Relative Strength Index) within N periods

        calculated based on the formula at:
        https://en.wikipedia.org/wiki/Relative_strength_index
        """
        self[meta.name] = self._rsi(meta.int)

    def _get_stochrsi(self, meta: _Meta):
        """ Calculate the Stochastic RSI

        calculated based on the formula at:
        https://www.investopedia.com/terms/s/stochrsi.asp
        """
        window = meta.int
        rsi = self._rsi(window)
        rsi_min = self.mov_min(rsi, window)
        rsi_max = self.mov_max(rsi, window)

        cv = (rsi - rsi_min) / (rsi_max - rsi_min)
        self[meta.name] = cv * 100

    def _wt1(self, n1: int, n2: int) -> pd.Series:
        """ wave trand 1

        n1: period of EMA on typical price
        n2: period of EMA
        """
        tp = self._tp()
        esa = self.ema(tp, n1)
        d = self.ema((tp - esa).abs(), n1)
        ci = (tp - esa) / (0.015 * d)
        return self.ema(ci, n2)

    def _get_wt1(self, meta: _Meta):
        self[meta.name] = self._wt1(meta.int0, meta.int1)

    def _get_wt2(self, meta: _Meta):
        wt1 = self._wt1(meta.int0, meta.int1)
        self[meta.name] = self.sma(wt1, 4)

    def _get_wt(self, meta: _Meta):
        """ Calculate LazyBear's Wavetrend
        Check the algorithm described below:
        https://medium.com/@samuel.mcculloch/lets-take-a-look-at-wavetrend-with-crosses-lazybear-s-indicator-2ece1737f72f
        """
        tci = self._wt1(meta.int0, meta.int1)
        self[meta.name_ex('1')] = tci
        self[meta.name_ex('2')] = self.sma(tci, 4)

    @staticmethod
    def smma(series, window):
        return series.ewm(
            ignore_na=False,
            alpha=1.0 / window,
            min_periods=0,
            adjust=True).mean()

    def _get_smma(self, meta: _Meta):
        """ get smoothed moving average """
        self[meta.name] = self.smma(self[meta.column], meta.int)

    def _get_trix(self, meta: _Meta):
        """ Triple Exponential Average

        https://www.investopedia.com/articles/technical/02/092402.asp
        """
        window = meta.int
        single = self.ema(self[meta.column], window)
        double = self.ema(single, window)
        triple = self.ema(double, window)
        prev_triple = self.s_shift(triple, -1)
        triple_change = self._delta(triple, -1)
        self[meta.name] = triple_change * 100 / prev_triple

    def _get_tema(self, meta: _Meta):
        """ Another implementation for triple ema

        Check the algorithm described below:
        https://www.forextraders.com/forex-education/forex-technical-analysis/triple-exponential-moving-average-the-tema-indicator/
        """
        window = meta.int
        single = self.ema(self[meta.column], window)
        double = self.ema(single, window)
        triple = self.ema(double, window)
        self[meta.name] = 3.0 * single - 3.0 * double + triple

    def _get_wr(self, meta: _Meta):
        """ Williams Overbought/Oversold Index

        Definition: https://www.investopedia.com/terms/w/williamsr.asp
        WMS=[(Hn—Ct)/(Hn—Ln)] × -100
        Ct - the close price
        Hn - N periods high
        Ln - N periods low
        """
        window = meta.int
        ln = self.mov_min(self.low, window)
        hn = self.mov_max(self.high, window)
        self[meta.name] = (hn - self.close) / (hn - ln) * -100

    def _get_cci(self, meta: _Meta):
        """ Commodity Channel Index

        CCI = (Typical Price  -  20-period SMA of TP) / (.015 x Mean Deviation)
        * when amount is not available:
          Typical Price (TP) = (High + Low + Close)/3
        * when amount is available:
          Typical Price (TP) = Amount / Volume
        TP is also implemented as 'middle'.
        """
        window = meta.int
        tp = self._tp()
        tp_sma = self.sma(tp, window)
        mad = self._mad(tp, window)
        self[meta.name] = (tp - tp_sma) / (.015 * mad)

    def _tr(self):
        prev_close = self.s_shift(self['close'], -1)
        high = self.high
        low = self.low
        c1 = high - low
        c2 = (high - prev_close).abs()
        c3 = (low - prev_close).abs()
        return pd.concat((c1, c2, c3), axis=1).max(axis=1)

    def _get_tr(self, meta: _Meta):
        """ True Range of the trading

         TR is a measure of volatility of a High-Low-Close series

        tr = max[(high - low), abs(high - close_prev), abs(low - close_prev)]

        :return: None
        """
        self[meta.name] = self._tr()

    def _get_supertrend(self, meta: _Meta):
        """ Supertrend

        Supertrend indicator shows trend direction.
        It provides buy or sell indicators.
        https://medium.com/codex/step-by-step-implementation-of-the-supertrend-indicator-in-python-656aa678c111
        """
        window = meta.int
        high = self.high
        low = self.low
        close = self.close
        m_atr = self.SUPERTREND_MUL * self._atr(window)
        hl_avg = (high + low) / 2.0
        # basic upper band
        b_ub = list(hl_avg + m_atr)
        # basic lower band
        b_lb = list(hl_avg - m_atr)

        size = len(close)
        ub = np.empty(size, dtype=np.float64)
        lb = np.empty(size, dtype=np.float64)
        st = np.empty(size, dtype=np.float64)
        close = list(close)

        for i in range(size):
            if i == 0:
                ub[i] = b_ub[i]
                lb[i] = b_lb[i]
                if close[i] <= ub[i]:
                    st[i] = ub[i]
                else:
                    st[i] = lb[i]
                continue

            last_close = close[i - 1]
            curr_close = close[i]
            last_ub = ub[i - 1]
            last_lb = lb[i - 1]
            last_st = st[i - 1]
            curr_b_ub = b_ub[i]
            curr_b_lb = b_lb[i]

            # calculate current upper band
            if curr_b_ub < last_ub or last_close > last_ub:
                ub[i] = curr_b_ub
            else:
                ub[i] = last_ub

            # calculate current lower band
            if curr_b_lb > last_lb or last_close < last_lb:
                lb[i] = curr_b_lb
            else:
                lb[i] = last_lb

            # calculate supertrend
            if last_st == last_ub:
                if curr_close <= last_ub:
                    st[i] = ub[i]
                else:
                    st[i] = lb[i]
            elif last_st == last_lb:
                if curr_close > last_lb:
                    st[i] = lb[i]
                else:
                    st[i] = ub[i]

        self[f'{meta.name}_ub'] = ub
        self[f'{meta.name}_lb'] = lb
        self[f'{meta.name}'] = st

    def _get_aroon(self, meta: _Meta):
        """ Aroon Oscillator

        The Aroon Oscillator measures the strength of a trend and
        the likelihood that it will continue.

        The default window is 25.

        * Aroon Oscillator = Aroon Up - Aroon Down
        * Aroon Up = 100 * (n - periods since n-period high) / n
        * Aroon Down = 100 * (n - periods since n-period low) / n
        * n = window size
        """
        window = meta.int

        def _window_pct(s):
            n = float(window)
            return (n - (n - (s + 1))) / n * 100

        high_since = self._rolling(
            self.high, window).apply(np.argmax, raw=True)
        low_since = self._rolling(
            self.low, window).apply(np.argmin, raw=True)

        aroon_up = _window_pct(high_since)
        aroon_down = _window_pct(low_since)
        self[meta.name] = aroon_up - aroon_down

    def _get_z(self, meta: _Meta):
        """ Z score

        Z-score is a statistical measurement that describes a value's
        relationship to the mean of a group of values.

        The statistical formula for a value's z-score is calculated using
        the following formula:

        z = ( x - μ ) / σ

        Where:

        * z = Z-score
        * x = the value being evaluated
        * μ = the mean
        * σ = the standard deviation
        """
        window = meta.int
        col = self[meta.column]
        mean = self.sma(col, window)
        std = self.mov_std(col, window)
        value = (col - mean) / std
        if len(value) > 1:
            value.iloc[0] = value.iloc[1]
        self[meta.name] = value

    def _atr(self, window):
        tr = self._tr()
        return self.smma(tr, window)

    def _get_atr(self, meta: _Meta):
        """ Average True Range

        The average true range is an N-day smoothed moving average (SMMA) of
        the true range values.  Default to 14 periods.
        https://en.wikipedia.org/wiki/Average_true_range
        """
        window = meta.int
        self[meta.name] = self._atr(window)

    def _get_dma(self, meta: _Meta):
        """ Difference of Moving Average

        default to 10 and 50.

        :return: None
        """
        fast = meta.int0
        slow = meta.int1
        col = self[meta.column]
        diff = self.sma(col, fast) - self.sma(col, slow)
        self[meta.name] = diff

    def _get_dmi(self, _: _Meta):
        """ get the default setting for DMI

        including:
        +DI: 14 periods SMMA of +DM,
        -DI: 14 periods SMMA of -DM,
        DX: based on +DI and -DI
        ADX: 6 periods SMMA of DX

        :return:
        """
        self['dx'] = self._dx(self.DX_SMMA)
        self['adx'] = self.ema(self['dx'], self.ADX_EMA)
        self['adxr'] = self.ema(self['adx'], self.ADXR_EMA)

    def _get_pdm_ndm(self, window):
        hd = self._col_diff('high')
        ld = -self._col_diff('low')
        p = ((hd > 0) & (hd > ld)) * hd
        n = ((ld > 0) & (ld > hd)) * ld
        if window > 1:
            p = self.smma(p, window)
            n = self.smma(n, window)
        return p, n

    def _pdm(self, window):
        ret, _ = self._get_pdm_ndm(window)
        return ret

    def _ndm(self, window):
        _, ret = self._get_pdm_ndm(window)
        return ret

    def _get_pdm(self, meta: _Meta):
        """ +DM, positive directional moving

        If window is not 1, calculate the SMMA of +DM
        """
        self[meta.name] = self._pdm(meta.int)

    def _get_ndm(self, meta: _Meta):
        """ -DM, negative directional moving accumulation

        If window is not 1, return the SMA of -DM.
        """
        self[meta.name] = self._ndm(meta.int)

    def _get_vr(self, meta: _Meta):
        """ VR - Volume Variation Index """
        window = meta.int
        idx = self.index
        gt_zero = np.where(self['change'] > 0, self.volume, 0)
        av = pd.Series(gt_zero, index=idx)
        avs = self.mov_sum(av, window)

        lt_zero = np.where(self['change'] < 0, self.volume, 0)
        bv = pd.Series(lt_zero, index=idx)
        bvs = self.mov_sum(bv, window)

        eq_zero = np.where(self['change'] == 0, self.volume, 0)
        cv = pd.Series(eq_zero, index=idx)
        cvs = self.mov_sum(cv, window)

        self[meta.name] = (avs + cvs / 2) / (bvs + cvs / 2) * 100

    def _get_pdi_ndi(self, window):
        pdm, ndm = self._get_pdm_ndm(window)
        atr = self._atr(window)
        pdi = pdm / atr * 100
        ndi = ndm / atr * 100
        return pdi, ndi

    def _get_pdi(self, meta: _Meta):
        """ +DI, positive directional moving index """
        pdi, _ = self._get_pdi_ndi(meta.int)
        self[meta.name] = pdi
        return pdi

    def _get_ndi(self, meta: _Meta):
        """ -DI, negative directional moving index """
        _, ndi = self._get_pdi_ndi(meta.int)
        self[meta.name] = ndi
        return ndi

    def _dx(self, window):
        pdi, mdi = self._get_pdi_ndi(window)
        return abs(pdi - mdi) / (pdi + mdi) * 100

    def _get_dx(self, meta: _Meta):
        self[meta.name] = self._dx(meta.int)

    def _get_cr(self, meta: _Meta):
        """ Energy Index (Intermediate Willingness Index)

        https://support.futunn.com/en/topic167/?lang=en-us
        Use the relationship between the highest price, the lowest price and
        yesterday's middle price to reflect the market's willingness to buy
        and sell.
        """
        window = meta.int
        middle = self._tp()
        last_middle = self.s_shift(middle, -1)
        ym = self.s_shift(middle, -1)
        high = self.high
        low = self.low
        p1_m = pd.concat((last_middle, high), axis=1).min(axis=1)
        p2_m = pd.concat((last_middle, low), axis=1).min(axis=1)
        p1 = self.mov_sum(high - p1_m, window)
        p2 = self.mov_sum(ym - p2_m, window)

        name = meta.name
        self[name] = cr = p1 / p2 * 100
        self[f'{name}-ma1'] = self._shifted_cr_sma(cr, self.CR_MA[0])
        self[f'{name}-ma2'] = self._shifted_cr_sma(cr, self.CR_MA[1])
        self[f'{name}-ma3'] = self._shifted_cr_sma(cr, self.CR_MA[2])

    def _shifted_cr_sma(self, cr, window):
        cr_sma = self.sma(cr, window)
        return self.s_shift(cr_sma, -int(window / 2.5 + 1))

    def _tp(self):
        if 'amount' in self:
            return self.amount / self.volume
        return (self.close + self.high + self.low).divide(3.0)

    def _get_tp(self, meta: _Meta):
        self[meta.name] = self._tp()

    def _get_middle(self, meta: _Meta):
        self[meta.name] = self._tp()

    def _calc_kd(self, column):
        param0, param1 = self.KDJ_PARAM
        k = 50.0
        # noinspection PyTypeChecker
        for i in param1 * column:
            k = param0 * k + i
            yield k

    def _get_kdjk(self, meta: _Meta):
        """ Get the K of KDJ

        K ＝ 2/3 × (prev. K) +1/3 × (curr. RSV)
        2/3 and 1/3 are the smooth parameters.
        """
        window = meta.int
        rsv = self._rsv(window)
        self[meta.name] = list(self._calc_kd(rsv))

    def _get_kdjd(self, meta: _Meta):
        """ Get the D of KDJ

        D = 2/3 × (prev. D) +1/3 × (curr. K)
        2/3 and 1/3 are the smooth parameters.
        """
        k_column = meta.name.replace('kdjd', 'kdjk')
        self[meta.name] = list(self._calc_kd(self.get(k_column)))

    def _get_kdjj(self, meta: _Meta):
        """ Get the J of KDJ

        J = 3K-2D
        """
        k_column = meta.name.replace('kdjj', 'kdjk')
        d_column = meta.name.replace('kdjj', 'kdjd')
        self[meta.name] = 3 * self[k_column] - 2 * self[d_column]

    @staticmethod
    def _delta(series, window):
        return series.diff(-window).fillna(0.0)

    def _get_d(self, meta: _Meta):
        self[meta.name] = self._delta(self[meta.column], meta.int)

    @classmethod
    def mov_min(cls, series, size):
        return cls._rolling(series, size).min()

    @classmethod
    def mov_max(cls, series, size):
        return cls._rolling(series, size).max()

    @classmethod
    def mov_sum(cls, series, size):
        return cls._rolling(series, size).sum()

    @classmethod
    def sma(cls, series, size):
        return cls._rolling(series, size).mean()

    @staticmethod
    def roc(series, size):
        ret = series.diff(size) / series.shift(size)
        if size < 0:
            ret.iloc[size:] = 0
        else:
            ret.iloc[:size] = 0
        return ret * 100

    @classmethod
    def _mad(cls, series, window):
        """ Mean Absolute Deviation

        :param series: Series
        :param window: number of periods
        :return: Series
        """

        def f(x):
            return np.fabs(x - x.mean()).mean()

        return cls._rolling(series, window).apply(f, raw=True)

    def _get_mad(self, meta: _Meta):
        """ get mean absolute deviation """
        window = meta.int
        self[meta.name] = self._mad(self[meta.column], window)

    def _get_sma(self, meta: _Meta):
        """ get simple moving average """
        window = meta.int
        self[meta.name] = self.sma(self[meta.column], window)

    def _get_lrma(self, meta: _Meta):
        """ get linear regression moving average """
        window = meta.int
        self[meta.name] = self.linear_reg(self[meta.column], window)

    def _get_roc(self, meta: _Meta):
        """get Rate of Change (ROC) of a column

        The Price Rate of Change (ROC) is a momentum-based technical indicator
        that measures the percentage change in price between the current price
        and the price a certain number of periods ago.

        https://www.investopedia.com/terms/p/pricerateofchange.asp

        Formular:

        ROC = (PriceP - PricePn) / PricePn * 100

        Where:
        * PriceP: the price of the current period
        * PricePn: the price of the n periods ago
        """
        self[meta.name] = self.roc(self[meta.column], meta.int)

    @staticmethod
    def ema(series, window, *, adjust=True, min_periods=1):
        return series.ewm(
            ignore_na=False,
            span=window,
            min_periods=min_periods,
            adjust=adjust).mean()

    @staticmethod
    def _rolling(series: pd.Series, window: int):
        return series.rolling(window, min_periods=1, center=False)

    @classmethod
    def linear_wma(cls, series, window):
        total_weight = 0.5 * window * (window + 1)
        weights = np.arange(1, window + 1) / total_weight

        def linear(w):
            def _compute(x):
                try:
                    return np.dot(x, w)
                except ValueError:
                    return 0.0

            return _compute

        rolling = cls._rolling(series, window)
        return rolling.apply(linear(weights), raw=True)

    @classmethod
    def linear_reg(cls,
                   series,
                   window,
                   correlation=False):
        window = cls.get_int_positive(window)

        x = range(1, window + 1)
        x_sum = 0.5 * window * (window + 1)
        x2_sum = x_sum * (2 * window + 1) / 3
        divisor = window * x2_sum - x_sum * x_sum

        def linear_regression(s: pd.Series):
            y_sum = s.sum()
            xy_sum = (x * s).sum()

            m = (window * xy_sum - x_sum * y_sum) / divisor
            b = (y_sum * x2_sum - x_sum * xy_sum) / divisor

            if correlation:
                y2_sum = (s * s).sum()
                rn = window * xy_sum - x_sum * y_sum
                rd = (divisor * (window * y2_sum - y_sum * y_sum)) ** 0.5
                return rn / rd
            return m * (window - 1) + b

        def rolling(arr):
            strides = arr.strides + (arr.strides[-1],)
            shape = arr.shape[:-1] + (arr.shape[-1] - window + 1, window)
            return as_strided(arr, shape=shape, strides=strides)

        value = [linear_regression(_)
                 for _ in rolling(np.array(series))]
        ret = pd.Series([0.0] * (window - 1) + value,
                        index=series.index)
        return ret

    def _get_cti(self, meta: _Meta):
        """ get correlation trend indicator

        Correlation Trend Indicator is a study that estimates
        the current direction and strength of a trend.
        https://tlc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/C-D/CorrelationTrendIndicator
        """
        value = self.linear_reg(
            self[meta.column], meta.int, correlation=True)
        self[meta.name] = value

    def _get_ema(self, meta: _Meta):
        """ get exponential moving average """
        self[meta.name] = self.ema(self[meta.column], meta.int)

    def _get_boll(self, meta: _Meta):
        """ Get Bollinger bands.

        boll_ub means the upper band of the Bollinger bands
        boll_lb means the lower band of the Bollinger bands
        boll_ub = MA + Kσ
        boll_lb = MA − Kσ
        M = BOLL_PERIOD
        K = BOLL_STD_TIMES
        :return: None
        """
        n = meta.int
        boll = meta.name
        boll_ub = meta.name_ex('_ub')
        boll_lb = meta.name_ex('_lb')
        moving_avg = self.sma(self.close, n)
        moving_std = self.mov_std(self.close, n)

        self[boll] = moving_avg
        width = self.BOLL_STD_TIMES * moving_std
        self[boll_ub] = moving_avg + width
        self[boll_lb] = moving_avg - width

    def _get_macd(self, meta: _Meta):
        """ Moving Average Convergence Divergence

        This function will initialize all following columns.

        MACD Line (macd): (12-day EMA - 26-day EMA)
        Signal Line (macds): 9-day EMA of MACD Line
        MACD Histogram (macdh): MACD Line - Signal Line
        """
        close = self.close
        short_w, long_w, signal_w = meta.int0, meta.int1, meta.int2
        ema_short = self.ema(close, short_w)
        ema_long = self.ema(close, long_w)
        macd = meta.name
        macds = meta.name_ex('s')
        macdh = meta.name_ex('h')
        self[macd] = ema_short - ema_long
        self[macds] = self.ema(self[macd], signal_w)
        self[macdh] = self[macd] - self[macds]

    def _ppo_and_pvo(self, name: str, col_name: str, meta: _Meta):
        volume = self[col_name]
        short_w, long_w, signal_w = meta.int0, meta.int1, meta.int2
        pvo_short = self.ema(volume, short_w)
        pvo_long = self.ema(volume, long_w)
        self[name] = (pvo_short - pvo_long) / pvo_long * 100
        self[f'{name}s'] = self.ema(self[name], signal_w)
        self[f'{name}h'] = self[name] - self[f'{name}s']

    def _get_pvo(self, meta: _Meta):
        """ Percentage Volume Oscillator

        The Percentage Volume Oscillator (PVO) is a momentum oscillator for
        volume.  The PVO measures the difference between two volume-based
        moving averages as a percentage of the larger moving average.

        https://school.stockcharts.com/doku.php?id=technical_indicators:percentage_volume_oscillator_pvo

        Percentage Volume Oscillator (PVO):
            {(12_EOV - 26_EOV)/26_EOV} x 100

        Where:
        * 12_EOV is the 12-day EMA of Volume
        * 26_EOV is the 26-day EMA of Volume

        Signal Line: 9-day EMA of PVO

        PVO Histogram: PVO - Signal Line
        """
        return self._ppo_and_pvo('pvo', 'volume', meta)

    def _get_ppo(self, meta: _Meta):
        """ Percentage Price Oscillator

        https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:price_oscillators_ppo

        Percentage Price Oscillator (PPO):
            {(12-day EMA - 26-day EMA)/26-day EMA} x 100

        Signal Line: 9-day EMA of PPO

        PPO Histogram: PPO - Signal Line
        """
        return self._ppo_and_pvo('ppo', 'close', meta)

    def _eri(self, window):
        ema = self.ema(self.close, window, adjust=False)
        bull = self.high - ema
        bear = self.low - ema
        return bull, bear

    def _get_eribull(self, meta: _Meta):
        """ The bull line of Elder-Ray Index """
        bull, _ = self._eri(meta.int)
        self[meta.name] = bull
        return bull

    def _get_eribear(self, meta: _Meta):
        """ The bear line of Elder-Ray Index """
        _, bear = self._eri(meta.int)
        self[meta.name] = bear
        return bear

    def _get_eri(self, meta: _Meta):
        """ The Elder-Ray Index

        The Elder-Ray Index contains the bull and the bear power.
        Both are calculated based on the EMA of the close price.

        The default window is 13.

        https://admiralmarkets.com/education/articles/forex-indicators/bears-and-bulls-power-indicator

        Formular:
        * Bulls Power = High - EMA
        * Bears Power = Low - EMA
        * EMA is exponential moving average of close of N periods
        """
        bull, bear = self._eri(meta.int)
        self[meta.name_ex('bull')] = bull
        self[meta.name_ex('bear')] = bear

    def _get_coppock(self, meta: _Meta):
        """ Get Coppock Curve

        Coppock Curve is a momentum indicator that signals
        long-term trend reversals.

        https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:coppock_curve
        """
        window, fast, slow = meta.int0, meta.int1, meta.int2
        fast_roc = self.roc(self.close, fast)
        slow_roc = self.roc(self.close, slow)
        roc_ema = self.linear_wma(fast_roc + slow_roc, window)
        self[meta.name] = roc_ema

    @classmethod
    def get_int_positive(cls, windows):
        if isinstance(windows, int):
            window = windows
        else:
            window = cls.to_int(windows)
            if window <= 0:
                raise IndexError("window must be greater than 0")
        return window

    def _hl_mid(self, period):
        ph = self.mov_max(self.high, period)
        pl = self.mov_min(self.low, period)
        return (ph + pl) * 0.5

    def _get_ichimoku(self, meta: _Meta):
        """ get Ichimoku Cloud

        The Ichimoku Cloud is a collection of technical indicators
        that show support and resistance levels, as well as momentum
        and trend direction.

        In this implementation, we only calculate the delta between
        lead A and lead B.

        https://www.investopedia.com/terms/i/ichimoku-cloud.asp

        It contains three windows:
        * window for the conversion line, default to 9
        * window for the baseline and the shifts, default to 26
        * window for the leading line, default to 52

        Formular:
        * conversion line = (PH9 + PL9) / 2
        * baseline = (PH26 + PL26) / 2
        * leading span A = (conversion line + baseline) / 2
        * leading span B = (PH52 + PL52) / 2
        * result = leading span A - leading span B

        Where:
        * PH = Period High
        * PL = Period Low

        """
        conv, base, lead = meta.int0, meta.int1, meta.int2
        conv_line = self._hl_mid(conv)
        base_line = self._hl_mid(base)
        lead_a = (conv_line + base_line) * 0.5
        lead_b = self._hl_mid(lead)

        lead_a_s = lead_a.shift(base, fill_value=lead_a.iloc[0])
        lead_b_s = lead_b.shift(base, fill_value=lead_b.iloc[0])
        self[meta.name] = lead_a_s - lead_b_s

    @classmethod
    def mov_std(cls, series, window):
        return cls._rolling(series, window).std()

    def _get_mstd(self, meta: _Meta):
        """ get moving standard deviation """
        self[meta.name] = self.mov_std(self[meta.column], meta.int)

    @classmethod
    def mov_var(cls, series, window):
        return cls._rolling(series, window).var()

    def _get_mvar(self, meta: _Meta):
        """ get moving variance """
        self[meta.name] = self.mov_var(self[meta.column], meta.int)

    def _get_vwma(self, meta: _Meta):
        """ get Volume Weighted Moving Average

        The definition is available at:
        https://www.investopedia.com/articles/trading/11/trading-with-vwap-mvwap.asp
        """
        window = meta.int
        tpv = self.volume * self._tp()
        rolling_tpv = self.mov_sum(tpv, window)
        rolling_vol = self.mov_sum(self.volume, window)
        self[meta.name] = rolling_tpv / rolling_vol

    def _get_chop(self, meta: _Meta):
        """ get Choppiness Index (CHOP)

        See the definition of the index here:
        https://www.tradingview.com/education/choppinessindex/

        Calculation:

        100 * LOG10( SUM(ATR(1), n) / ( MaxHi(n) - MinLo(n) ) ) / LOG10(n)
        n = User defined period length.
        LOG10(n) = base-10 LOG of n
        ATR(1) = Average True Range (Period of 1)
        SUM(ATR(1), n) = Sum of the Average True Range over past n bars
        MaxHi(n) = The highest high over past n bars
        """
        window = meta.int
        atr = self._atr(1)
        atr_sum = self.mov_sum(atr, window)
        high = self.mov_max(self.high, window)
        low = self.mov_min(self.low, window)
        choppy = atr_sum / (high - low)
        numerator = np.log10(choppy) * 100
        denominator = np.log10(window)
        self[meta.name] = numerator / denominator

    def _get_mfi(self, meta: _Meta):
        """ get money flow index

        The definition of money flow index is available at:
        https://www.investopedia.com/terms/m/mfi.asp
        """
        window = meta.int
        middle = self._tp()
        money_flow = (middle * self["volume"]).fillna(0.0)
        shifted = self.s_shift(middle, -1)
        delta = (middle - shifted).fillna(0)
        pos_flow = money_flow.mask(delta < 0, 0)
        neg_flow = money_flow.mask(delta >= 0, 0)
        rolling_pos_flow = self.mov_sum(pos_flow, window)
        rolling_neg_flow = self.mov_sum(neg_flow, window)
        money_flow_ratio = rolling_pos_flow / (rolling_neg_flow + 1e-12)
        mfi = (1.0 - 1.0 / (1 + money_flow_ratio))
        mfi.iloc[:window] = 0.5
        self[meta.name] = mfi

    def _get_ao(self, meta: _Meta):
        """ get awesome oscillator

        The AO indicator is a good indicator for measuring the market dynamics,
        it reflects specific changes in the driving force of the market, which
        helps to identify the strength of the trend, including the points of
        its formation and reversal.


        Awesome Oscillator Formula
        * MEDIAN PRICE = (HIGH+LOW)/2
        * AO = SMA(MEDIAN PRICE, 5)-SMA(MEDIAN PRICE, 34)

        https://www.ifcm.co.uk/ntx-indicators/awesome-oscillator
        """
        fast = meta.int0
        slow = meta.int1
        median_price = (self.high + self.low) * 0.5
        ao = self.sma(median_price, fast) - self.sma(median_price, slow)
        self[meta.name] = ao

    def _get_bop(self, meta: _Meta):
        """ get balance of power

        The Balance of Power indicator measures the strength of the bulls.
        https://school.stockcharts.com/doku.php?id=technical_indicators:balance_of_power

        BOP = (close - open) / (high - low)
        """
        dividend = self.close - self.open
        divisor = self.high - self.low
        self[meta.name] = dividend / divisor

    def _get_cmo(self, meta: _Meta):
        """ get Chande Momentum Oscillator

        The Chande Momentum Oscillator (CMO) is a technical momentum
        indicator developed by Tushar Chande.
        https://www.investopedia.com/terms/c/chandemomentumoscillator.asp

        CMO = 100 * ((sH - sL) / (sH + sL))

        where:
        * sH=the sum of higher closes over N periods
        * sL=the sum of lower closes of N periods
        """
        window = meta.int
        close_diff = self._col_diff('close')
        up = close_diff.clip(lower=0)
        down = close_diff.clip(upper=0).abs()
        sum_up = self.mov_sum(up, window)
        sum_down = self.mov_sum(down, window)
        dividend = sum_up - sum_down
        divisor = sum_up + sum_down
        res = 100 * dividend / divisor
        res.iloc[0] = 0.0
        self[meta.name] = res

    def ker(self, column, window):
        col = self[column]
        col_window_s = self.s_shift(col, -window)
        window_diff = (col - col_window_s).abs()
        diff = self._col_diff(column).abs()
        volatility = self.mov_sum(diff, window)
        ret = window_diff / volatility
        ret.iloc[0] = 0
        return ret

    def _get_ker(self, meta: _Meta):
        """ get Kaufman's efficiency ratio

        The Efficiency Ratio (ER) is calculated by
        dividing the price change over a period by the
        absolute sum of the price movements that occurred
        to achieve that change.
        The resulting ratio ranges between 0 and 1 with
        higher values representing a more efficient or
        trending market.

        The default column is close.
        The default window is 10.

        https://strategyquant.com/codebase/kaufmans-efficiency-ratio-ker/

        Formular:
        window_change = ABS(close - close[n])
        last_change = ABS(close-close[1])
        volatility = moving sum of last_change in n
        KER = window_change / volatility
        """
        self[meta.name] = self.ker(meta.column, meta.int)

    def _get_kama(self, meta: _Meta):
        """ get Kaufman's Adaptive Moving Average.
        Implemented after
        https://school.stockcharts.com/doku.php?id=technical_indicators:kaufman_s_adaptive_moving_average
        """
        window, fast, slow = meta.int0, meta.int1, meta.int2
        efficiency_ratio = self.ker(meta.column, window)
        fast_ema_smoothing = 2.0 / (fast + 1)
        slow_ema_smoothing = 2.0 / (slow + 1)
        smoothing_2 = fast_ema_smoothing - slow_ema_smoothing
        efficient_smoothing = efficiency_ratio * smoothing_2
        smoothing = list(2 * (efficient_smoothing + slow_ema_smoothing))

        # start with simple moving average
        col = self[meta.column]
        kama = list(self.sma(col, window))
        if len(kama) >= window:
            last_kama = kama[window - 1]
        else:
            last_kama = 0.0

        col_list = list(col)
        for i in range(window, len(kama)):
            cur = smoothing[i] * (col_list[i] - last_kama) + last_kama
            kama[i] = cur
            last_kama = cur
        self[meta.name] = kama

    def _ftr(self, window: int) -> pd.Series:
        mp = (self.high + self.low) * 0.5
        highest = mp.rolling(window).max()
        lowest = mp.rolling(window).min()
        width = highest - lowest
        width[width < 0.001] = 0.001
        position = list(((mp - lowest) / width) - 0.5)

        v = 0
        size = self.high.size
        result = np.zeros(size)
        for i in range(window, size):
            v = 0.66 * position[i] + 0.67 * v
            if v < -0.99:
                v = -0.999
            if v > 0.99:
                v = 0.999
            r = 0.5 * (np.log((1 + v) / (1 - v)) + result[i - 1])
            result[i] = r
        return pd.Series(result, index=self.index)

    def _get_ftr(self, meta: _Meta):
        """ the Gaussian Fisher Transform Price Reversals indicator

        The Gaussian Fisher Transform Price Reversals indicator, dubbed
        FTR for short, is a stat based price reversal detection indicator
        inspired by and based on the work of the electrical engineer
        now private trader John F. Ehlers.

        https://www.tradingview.com/script/ajZT2tZo-Gaussian-Fisher-Transform-Price-Reversals-FTR/

        Implementation reference:

        https://github.com/twopirllc/pandas-ta/blob/084dbe1c4b76082f383fa3029270ea9ac35e4dc7/pandas_ta/momentum/fisher.py#L9

        Formular:
        * Fisher Transform = 0.5 * ln((1 + X) / (1 - X))
        * X is a series whose values are between -1 to 1
        """
        self[meta.name] = self._ftr(meta.int)

    @staticmethod
    def sym_wma4(series: pd.Series) -> pd.Series:
        arr = np.array([1, 2, 2, 1])
        weights = arr / sum(arr)
        rolled = series.rolling(arr.size)
        ret = rolled.apply(lambda x: np.dot(x, weights), raw=True)
        ret.iloc[:arr.size - 1] = 0.0
        return ret

    def _rvgi(self, window: int) -> pd.Series:
        """ Relative Vigor Index (RVGI)

        The Relative Vigor Index (RVI) is a momentum indicator
        used in technical analysis that measures the strength
        of a trend by comparing a security's closing price to
        its trading range while smoothing the results using a
        simple moving average (SMA).

        https://www.investopedia.com/terms/r/relative_vigor_index.asp

        Formular
        * NUMERATOR= (a+(2×b)+(2×c)+d) / 6
        * DENOMINATOR= (e+(2×f)+(2×g)+h) / 6
        * RVI= SMA-N of DENOMINATOR / SMA-N of NUMERATOR
        * Signal Line = (RVI+(2×i)+(2×j)+k) / 6

        where:
        * a=Close−Open
        * b=Close−Open One Bar Prior to a
        * c=Close−Open One Bar Prior to b
        * d=Close−Open One Bar Prior to c
        * e=High−Low of Bar a
        * f=High−Low of Bar b
        * g=High−Low of Bar c
        * h=High−Low of Bar d
        * i=RVI Value One Bar Prior
        * j=RVI Value One Bar Prior to i
        * k=RVI Value One Bar Prior to j
        * N=Minutes/Hours/Days/Weeks/Months
        """
        co = self.close - self.open
        hl = self.high - self.low

        nu = self.sym_wma4(co)
        de = self.sym_wma4(hl)
        ret = self.sma(nu, window) / self.sma(de, window)
        return ret

    def _get_rvgis(self, meta: _Meta):
        self._get_rvgi(meta.set_name('rvgi'))

    def _get_rvgi(self, meta: _Meta):
        rvgi = self._rvgi(meta.int)
        rvgi.iloc[:3] = 0.0
        rvgi_s = self.sym_wma4(rvgi)
        rvgi_s.iloc[:6] = 0.0
        self[meta.name] = rvgi
        self[meta.name_ex('s')] = rvgi_s

    def _inertia(self, window: int, rvgi_window: int) -> pd.Series:
        """ Inertia Indicator

        https://theforexgeek.com/inertia-indicator/

        In financial markets, the concept of inertia was given by Donald Dorsey
        in the 1995 issue of Technical Analysis of Stocks and Commodities
        through the Inertia Indicator. The Inertia Indicator is moment-based
        and is an extension of Dorsey’s Relative Volatility Index (RVI).
        """
        if len(self) < window + rvgi_window:
            return pd.Series(np.zeros(len(self)), index=self.index)
        rvgi = self._rvgi(rvgi_window)
        value = self.linear_reg(rvgi, window)
        value.iloc[:max(window, rvgi_window) + 2] = 0
        return value

    def _get_inertia(self, meta: _Meta):
        value = self._inertia(meta.int0, meta.int1)
        self[meta.name] = value

    def _kst(self) -> pd.Series:
        """ Know Sure Thing (kst)

        https://www.investopedia.com/terms/k/know-sure-thing-kst.asp

        The Know Sure Thing (KST) is a momentum oscillator developed by
        Martin Pring to make rate-of-change readings easier for traders
        to interpret.

        Formular:
        * KST=(RCMA #1×1)+(RCMA #2×2) + (RCMA #3×3)+(RCMA #4×4)

        where:
        * RCMA #1=10-period SMA of 10-period ROC
        * RCMA #2=10-period SMA of 15-period ROC
        * RCMA #3=10-period SMA of 20-period ROC
        * RCMA #4=15-period SMA of 30-period ROC
        """
        ma1 = self.sma(self.roc(self.close, 10), 10)
        ma2 = self.sma(self.roc(self.close, 15), 10)
        ma3 = self.sma(self.roc(self.close, 20), 10)
        ma4 = self.sma(self.roc(self.close, 30), 15)
        return ma1 + ma2 * 2 + ma3 * 3 + ma4 * 4

    def _get_kst(self, meta: _Meta):
        self[meta.name] = self._kst()

    def _pgo(self, window: int) -> pd.Series:
        """ Pretty Good Oscillator (PGO)

        https://library.tradingtechnologies.com/trade/chrt-ti-pretty-good-oscillator.html

        The Pretty Good Oscillator indicator by Mark Johnson measures the
        distance of the current close from its N-day simple moving average,
        expressed in terms of an average true range over a similar period.

        Formular:
        * PGO = (Close - SMA) / (EMA of TR)

        Where:
        * SMA = Simple Moving Average of Close over N periods
        * EMA of TR = Exponential Moving Average of True Range over N periods
        """
        up = self.close - self.sma(self.close, window)
        down = self.ema(self._tr(), window)
        return up / down

    def _get_pgo(self, meta: _Meta):
        self[meta.name] = self._pgo(meta.int)

    def _psl(self, col_name: str, window: int) -> pd.Series:
        """ Psychological Line (PSL)

        The Psychological Line indicator is the ratio of the number of
        rising periods over the total number of periods.

        https://library.tradingtechnologies.com/trade/chrt-ti-psychological-line.html

        Formular:
        * PSL = (Number of Rising Periods) / (Total Number of Periods) * 100

        Example:
        * `df['psl']` retrieves the PSL with default window 12.
        * `df['psl_10']` retrieves the PSL with window 10.
        * `df['high_12_psl']` retrieves the PSL of high price with window 10.
        """
        col_diff = self._col_diff(col_name)
        pos = col_diff > 0
        return self.mov_sum(pos, window) / window * 100

    def _get_psl(self, meta: _Meta):
        self[meta.name] = self._psl(meta.column, meta.int)

    def _get_qqe(self, meta: _Meta):
        """ QQE (Quantitative Qualitative Estimation)

        https://www.tradingview.com/script/0vn4HZ7O-Quantitative-Qualitative-Estimation-QQE/

        The Qualitative Quantitative Estimation (QQE) indicator works like a
        smoother version of the popular Relative Strength Index (RSI)
        indicator. QQE expands on RSI by adding two volatility based trailing
        stop lines. These trailing stop lines are composed of a fast and a
        slow moving Average True Range (ATR).  These ATR lines are smoothed
        making this indicator less susceptible to short term volatility.

        Implementation reference:
        https://github.com/twopirllc/pandas-ta/blob/main/pandas_ta/momentum/qqe.py

        """
        rsi_window = meta.int0
        rsi_ma_window = meta.int1
        factor = 4.236
        wilder_window = rsi_window * 2 - 1
        ema = functools.partial(self.ema, adjust=False)

        rsi = self._rsi(rsi_window)
        rsi.iloc[:rsi_window] = np.nan
        rsi_ma = ema(rsi, rsi_ma_window)
        tr = rsi_ma.diff().abs()
        tr_ma = ema(tr, wilder_window)
        tr_ma_ma = ema(tr_ma, wilder_window) * factor

        upper = list(rsi_ma + tr_ma_ma)
        lower = list(rsi_ma - tr_ma_ma)
        rsi_ma = list(rsi_ma)

        size = self.close.size
        long = [0] * size
        short = [0] * size
        trend = [1] * size
        qqe = [rsi_ma[0]] * size
        qqe_long = [np.nan] * size
        qqe_short = [np.nan] * size

        for i in range(1, size):
            c_rsi, p_rsi = rsi_ma[i], rsi_ma[i - 1]
            c_long, p_long = long[i - 1], long[i - 2]
            c_short, p_short = short[i - 1], short[i - 2]

            # Long Line
            if p_rsi > c_long and c_rsi > c_long:
                long[i] = max(c_long, lower[i])
            else:
                long[i] = lower[i]

            # Short Line
            if p_rsi < c_short and c_rsi < c_short:
                short[i] = min(c_short, upper[i])
            else:
                short[i] = upper[i]

            # Trend & QQE Calculation
            # Long: Current RSI_MA value Crosses the Prior Short Line Value
            # Short: Current RSI_MA Crosses the Prior Long Line Value
            rsi_ux_short = c_rsi > c_short and p_rsi < p_short
            rsi_dx_short = c_rsi <= c_short and p_rsi >= p_short
            rsi_ux_long = c_rsi > c_long and p_rsi < p_long
            rsi_dx_long = c_rsi <= c_long and p_rsi >= p_long
            if rsi_ux_short or rsi_dx_short:
                trend[i] = 1
                qqe[i] = qqe_long[i] = long[i]
            elif rsi_ux_long or rsi_dx_long:
                trend[i] = -1
                qqe[i] = qqe_short[i] = short[i]
            else:
                trend[i] = trend[i - 1]
                if trend[i] == 1:
                    qqe[i] = qqe_long[i] = long[i]
                else:
                    qqe[i] = qqe_short[i] = short[i]

        self[meta.name] = self.to_series(qqe)
        self[meta.name_ex('l')] = self.to_series(qqe_long)
        self[meta.name_ex('s')] = self.to_series(qqe_short)

    def _get_num(self, meta):
        split = meta.name.split(',')
        decimal_places = 0.0
        if (len(split) > 1):
            decimal_places_str = split[1]
            power = pow(0.1, len(decimal_places_str))
            decimal_places = float(decimal_places_str) * power
        self[meta.name] = meta.int0 + decimal_places

    def to_series(self, arr: list):
        return pd.Series(arr, index=self.close.index).fillna(0)

    @staticmethod
    def parse_column_name(name):
        m = re.match(r'(.*)_([\d\-+~,.]+)_(\w+)', name)
        ret = (None,)
        if m is None:
            m = re.match(r'(.*)_([\d\-+~,]+)', name)
            if m is not None:
                ret = m.group(1, 2)
        else:
            ret = m.group(1, 2, 3)
        return ret

    CROSS_COLUMN_MATCH_STR = '(.+)_(x|xu|xd)_(.+)'
    COMPARE_COLUMN_MATCH_STR = '(.+)_(le|ge|lt|gt|eq|ne)_(.+)'

    @classmethod
    def is_cross_columns(cls, name):
        return re.match(cls.CROSS_COLUMN_MATCH_STR, name) is not None

    @classmethod
    def is_compare_columns(cls, name):
        return re.match(cls.COMPARE_COLUMN_MATCH_STR, name) is not None

    @classmethod
    def parse_cross_column(cls, name):
        m = re.match(cls.CROSS_COLUMN_MATCH_STR, name)
        ret = [None, None, None]
        if m is not None:
            ret = m.group(1, 2, 3)
        return ret

    @classmethod
    def parse_compare_column(cls, name):
        m = re.match(cls.COMPARE_COLUMN_MATCH_STR, name)
        ret = [None, None, None]
        if m is not None:
            ret = m.group(1, 2, 3)
        return ret

    def _get_rate(self, _: _Meta):
        """ same as percent """
        self['rate'] = self.close.pct_change() * 100

    def _col_diff(self, col):
        ret = self[col].diff()
        ret = self._df_to_series(ret)
        ret.iloc[0] = 0.0
        return ret

    def _get_delta(self, key):
        key_to_delta = key.replace('_delta', '')
        self[key] = self._col_diff(key_to_delta)
        return self[key]

    def _get_cross(self, key):
        left, op, right = StockDataFrame.parse_cross_column(key)
        lt_series = self[left] > self[right]
        # noinspection PyTypeChecker
        different = np.zeros_like(lt_series)
        if len(different) > 1:
            # noinspection PyTypeChecker
            different[1:] = np.diff(lt_series)
            different[0] = False
        if op == 'x':
            self[key] = different
        elif op == 'xu':
            self[key] = different & lt_series
        elif op == 'xd':
            self[key] = different & ~lt_series
        return self[key]

    def _get_compare(self, key):
        left, op, right = StockDataFrame.parse_compare_column(key)
        if op == 'le':
            self[key] = self[left] <= self[right]
        elif op == 'ge':
            self[key] = self[left] >= self[right]
        elif op == 'lt':
            self[key] = self[left] < self[right]
        elif op == 'gt':
            self[key] = self[left] > self[right]
        elif op == 'eq':
            self[key] = self[left] == self[right]
        elif op == 'ne':
            self[key] = self[left] != self[right]
        return self[key]

    def init_all(self):
        """ initialize all stats. in the handler """
        for handler in self.handler.values():
            _call_handler(handler)

    def drop_column(self, names=None, inplace=False):
        """ drop column by the name

        multiple names can be supplied in a list
        :return: StockDataFrame
        """
        if self.empty:
            return self
        ret = self.drop(names, axis=1, inplace=inplace)
        if inplace is True:
            return self
        return wrap(ret)

    def drop_tail(self, n, inplace=False):
        """ drop n rows from the tail

        :return: StockDataFrame
        """
        tail = self.tail(n).index
        ret = self.drop(tail, inplace=inplace)
        if inplace is True:
            return self
        return wrap(ret)

    def drop_head(self, n, inplace=False):
        """ drop n rows from the beginning

        :return: StockDataFrame
        """
        head = self.head(n).index
        ret = self.drop(head, inplace=inplace)
        if inplace is True:
            return self
        return wrap(ret)

    def _get_handler(self, name: str):
        return getattr(self, f'_get_{name}')

    @property
    def handler(self):
        ret = {
            ('rate',): self._get_rate,
            ('middle',): self._get_middle,
            ('tp',): self._get_tp,
            ('boll', 'boll_ub', 'boll_lb'): self._get_boll,
            ('macd', 'macds', 'macdh'): self._get_macd,
            ('pvo', 'pvos', 'pvoh'): self._get_pvo,
            ('ppo', 'ppos', 'ppoh'): self._get_ppo,
            ('qqe', 'qqel', 'qqes'): self._get_qqe,
            ('cr', 'cr-ma1', 'cr-ma2', 'cr-ma3'): self._get_cr,
            ('tr',): self._get_tr,
            ('dx', 'adx', 'adxr'): self._get_dmi,
            ('log-ret',): self._get_log_ret,
            ('wt1', 'wt2'): self._get_wt,
            ('supertrend',
             'supertrend_lb',
             'supertrend_ub'): self._get_supertrend,
            ('bop',): self._get_bop,
            ('cti',): self._get_cti,
            ('eribull', 'eribear'): self._get_eri,
            ('rvgi', 'rvgis'): self._get_rvgi,
            ('kst',): self._get_kst,
            ('num',): self._get_num,
        }
        for k in _dft_windows.keys():
            if k not in ret:
                ret[k] = self._get_handler(k)
        return ret

    def __init_not_exist_column(self, key):
        for names, handler in self.handler.items():
            if key in names:
                return _call_handler(handler)

        if key.endswith('_delta'):
            self._get_delta(key)
        elif self.is_cross_columns(key):
            self._get_cross(key)
        elif self.is_compare_columns(key):
            self._get_compare(key)
        else:
            ret = self.parse_column_name(key)
            if len(ret) == 3:
                col, n, name = ret
            elif len(ret) == 2:
                name, n = ret
                col = None
            else:
                raise UserWarning("Invalid number of return arguments "
                                  f"after parsing column name: '{key}'")
            meta = _Meta(name, windows=n, column=col)
            self._get_handler(name)(meta)

    def __init_column(self, key):
        if key not in self:
            if len(self) == 0:
                self[key] = []
            else:
                self.__init_not_exist_column(key)

    def __getitem__(self, item):
        try:
            result = wrap(super(StockDataFrame, self).__getitem__(item))
        except KeyError:
            try:
                if isinstance(item, list):
                    for column in item:
                        self.__init_column(column)
                else:
                    self.__init_column(item)
            except AttributeError:
                pass
            result = wrap(super(StockDataFrame, self).__getitem__(item))
        return result

    def till(self, end_date):
        return self[self.index <= end_date]

    def start_from(self, start_date):
        return self[self.index >= start_date]

    def within(self, start_date, end_date):
        return self.start_from(start_date).till(end_date)

    # noinspection PyFinal
    def copy(self, deep=True):
        return wrap(super(StockDataFrame, self).copy(deep))

    @staticmethod
    def _ensure_type(obj):
        """ override the method in pandas, omit the check

        This patch is not the perfect way but could make the lib work.
        """
        return obj

    @staticmethod
    def retype(value, index_column=None):
        """ if the input is a `DataFrame`, convert it to this class.

        :param index_column: name of the index column, default to `date`
        :param value: value to convert
        :return: this extended class
        """
        if index_column is None:
            index_column = 'date'

        if isinstance(value, StockDataFrame):
            return value
        elif isinstance(value, pd.DataFrame):
            value = value.rename(_lower_col_name, axis='columns')
            if index_column in value.columns:
                value.set_index(index_column, inplace=True)
            ret = StockDataFrame(value)
            return ret
        return value


def _lower_col_name(name):
    candidates = ('open', 'close', 'high', 'low', 'volume', 'amount')
    if name.lower() != name and name.lower() in candidates:
        return name.lower()
    return name
