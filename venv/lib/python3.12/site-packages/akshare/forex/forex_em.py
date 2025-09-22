#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/6/23 15:00
Desc: 东方财富网-行情中心-外汇市场-所有汇率
https://quote.eastmoney.com/center/gridlist.html#forex_all
"""

import pandas as pd
import requests

from akshare.forex.cons import symbol_market_map
from akshare.utils.func import fetch_paginated_data


def forex_spot_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-外汇市场-所有汇率-实时行情数据
    https://quote.eastmoney.com/center/gridlist.html#forex_all
    :return: 实时行情数据
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fs": "m:119,m:120,m:133",
        "fields": "f12,f13,f14,f1,f2,f4,f3,f152,f17,f18,f15,f16",
        "fid": "f3",
        "pn": "1",
        "pz": "100",
        "po": "1",
        "dect": "1",
        "wbp2u": "|0|0|0|web",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.rename(
        columns={
            "index": "序号",
            "f12": "代码",
            "f14": "名称",
            "f17": "今开",
            "f4": "涨跌额",
            "f3": "涨跌幅",
            "f2": "最新价",
            "f15": "最高",
            "f16": "最低",
            "f18": "昨收",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "今开",
            "最高",
            "最低",
            "昨收",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce")
    return temp_df


def forex_hist_em(symbol: str = "USDCNH") -> pd.DataFrame:
    """
    东方财富网-行情中心-外汇市场-所有汇率-历史行情数据
    https://quote.eastmoney.com/cnyrate/EURCNYC.html
    :param symbol: 品种代码；可以通过 ak.forex_spot_em() 来获取所有可获取历史行情数据的品种代码
    :type symbol: str
    :return: 历史行情数据
    :rtype: pandas.DataFrame
    """
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    market_code = symbol_market_map[symbol]
    params = {
        "secid": f"{market_code}.{symbol}",
        "klt": "101",
        "fqt": "1",
        "lmt": "50000",
        "end": "20500000",
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "forcect": 1,
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    temp_df["code"] = data_json["data"]["code"]
    temp_df["name"] = data_json["data"]["name"]
    temp_df.columns = [
        "日期",
        "今开",
        "最新价",
        "最高",
        "最低",
        "-",
        "-",
        "振幅",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "代码",
        "名称",
    ]
    temp_df = temp_df[
        [
            "日期",
            "代码",
            "名称",
            "今开",
            "最新价",
            "最高",
            "最低",
            "振幅",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    forex_spot_em_df = forex_spot_em()
    print(forex_spot_em_df)

    forex_hist_em_df = forex_hist_em(symbol="USDCNH")
    print(forex_hist_em_df)
