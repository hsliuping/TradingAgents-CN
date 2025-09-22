#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/9 23:00
Desc: 东方财富网-行情中心-沪深港通
https://quote.eastmoney.com/center/gridlist.html#ah_comparison
"""

import math

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm
from akshare.utils.func import fetch_paginated_data


def stock_zh_ah_spot_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-沪深港通-AH股比价-实时行情
    https://quote.eastmoney.com/center/gridlist.html#ah_comparison
    :return: 东方财富网-行情中心-沪深港通-AH股比价-实时行情
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "np": "1",
        "fltt": "1",
        "invt": "2",
        "fs": "b:DLMK0101",
        "fields": "f193,f191,f192,f12,f13,f14,f1,f2,f4,f3,f152,f186,f190,f187,f189,f188",
        "fid": "f3",
        "pn": "1",
        "pz": "100",
        "po": "1",
        "dect": "1",
        "wbp2u": "|0|0|0|web",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"].astype(int) + 1
    temp_df.rename(
        columns={
            "index": "序号",
            "f193": "名称",
            "f12": "H股代码",
            "f2": "最新价-HKD",
            "f3": "H股-涨跌幅",
            "f191": "A股代码",
            "f186": "最新价-RMB",
            "f187": "A股-涨跌幅",
            "f189": "比价",
            "f188": "溢价",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "名称",
            "H股代码",
            "最新价-HKD",
            "H股-涨跌幅",
            "A股代码",
            "最新价-RMB",
            "A股-涨跌幅",
            "比价",
            "溢价",
        ]
    ]
    temp_df["最新价-HKD"] = pd.to_numeric(temp_df["最新价-HKD"], errors="coerce") / 1000
    temp_df["H股-涨跌幅"] = pd.to_numeric(temp_df["H股-涨跌幅"], errors="coerce") / 100
    temp_df["最新价-RMB"] = pd.to_numeric(temp_df["最新价-RMB"], errors="coerce") / 100
    temp_df["A股-涨跌幅"] = pd.to_numeric(temp_df["A股-涨跌幅"], errors="coerce") / 100
    temp_df["比价"] = pd.to_numeric(temp_df["比价"], errors="coerce") / 100
    temp_df["溢价"] = pd.to_numeric(temp_df["溢价"], errors="coerce") / 100
    return temp_df


def stock_hsgt_sh_hk_spot_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-沪深港通-港股通(沪>港)-股票
    https://quote.eastmoney.com/center/gridlist.html#hk_sh_stocks
    :return: 东方财富网-行情中心-沪深港通-港股通(沪>港)-股票
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "np": "1",
        "fltt": "1",
        "invt": "2",
        "fs": "b:DLMK0144",
        "fields": "f12,f13,f14,f19,f1,f2,f4,f3,f152,f17,f18,f15,f16,f5,f6",
        "fid": "f12",
        "pn": "1",
        "pz": "100",
        "po": "1",
        "dect": "1",
        "wbp2u": "|0|0|0|web",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.rename(
        columns={
            "f12": "代码",
            "f14": "名称",
            "f2": "最新价",
            "f4": "涨跌额",
            "f3": "涨跌幅",
            "f17": "今开",
            "f15": "最高",
            "f16": "最低",
            "f18": "昨收",
            "f5": "成交量",
            "f6": "成交额",
        },
        inplace=True,
    )

    temp_df = temp_df[
        [
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "今开",
            "最高",
            "最低",
            "昨收",
            "成交量",
            "成交额",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce") / 1000
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce") / 1000
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce") / 100
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce") / 1000
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce") / 1000
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce") / 1000
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce") / 1000
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce") / 100000000
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce") / 100000000
    temp_df.sort_values(["代码"], ignore_index=True, inplace=True)
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"].astype(int) + 1
    temp_df.rename(columns={"index": "序号"}, inplace=True)
    return temp_df


if __name__ == "__main__":
    stock_zh_ah_spot_em_df = stock_zh_ah_spot_em()
    print(stock_zh_ah_spot_em_df)

    stock_hsgt_sh_hk_spot_em_df = stock_hsgt_sh_hk_spot_em()
    print(stock_hsgt_sh_hk_spot_em_df)
