#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/2/24 18:30
Desc: 东方财富网-行情中心-港股市场-知名港股
https://quote.eastmoney.com/center/gridlist.html#hk_wellknown
"""

import pandas as pd
import requests


def stock_hk_famous_spot_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-港股市场-知名港股
    https://quote.eastmoney.com/center/gridlist.html#hk_wellknown
    :return: 知名美股实时行情
    :rtype: pandas.DataFrame
    """
    url = "https://69.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "50000",
        "po": "1",
        "np": "2",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "dect": "1",
        "wbp2u": "|0|0|0|web",
        "fid": "f3",
        "fs": "b:DLMK0106",
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,"
        "f25,f26,f22,f33,f11,f62,f128,f136,f115,f152",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["diff"]).T
    temp_df.columns = [
        "_",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "成交量",
        "成交额",
        "_",
        "_",
        "_",
        "_",
        "_",
        "代码",
        "编码",
        "名称",
        "最高",
        "最低",
        "今开",
        "昨收",
        "总市值",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "市盈率",
        "_",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df.reset_index(inplace=True)
    temp_df["index"] = range(1, len(temp_df) + 1)
    temp_df.rename(columns={"index": "序号"}, inplace=True)
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
            "成交量",
            "成交额",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_hk_famous_spot_em_df = stock_hk_famous_spot_em()
    print(stock_hk_famous_spot_em_df)
