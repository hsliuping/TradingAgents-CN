#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/2/24 18:30
Desc: 东方财富网-行情中心-美股市场-知名美股
https://quote.eastmoney.com/center/gridlist.html#us_wellknown
"""

import pandas as pd
import requests


def stock_us_famous_spot_em(symbol: str = "科技类") -> pd.DataFrame:
    """
    东方财富网-行情中心-美股市场-知名美股
    https://quote.eastmoney.com/center/gridlist.html#us_wellknown
    :symbol: choice of {'科技类', '金融类', '医药食品类', '媒体类', '汽车能源类', '制造零售类'}
    :type: str
    :return: 知名美股实时行情
    :rtype: pandas.DataFrame
    """
    market_map = {
        "科技类": "0216",
        "金融类": "0217",
        "医药食品类": "0218",
        "媒体类": "0220",
        "汽车能源类": "0219",
        "制造零售类": "0221",
    }
    url = "https://69.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "50000",
        "po": "1",
        "np": "2",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": f"b:MK{market_map[symbol]}",
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
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "简称",
        "编码",
        "名称",
        "最高价",
        "最低价",
        "开盘价",
        "昨收价",
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
    temp_df["代码"] = temp_df["编码"].astype(str) + "." + temp_df["简称"]
    temp_df = temp_df[
        [
            "序号",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "开盘价",
            "最高价",
            "最低价",
            "昨收价",
            "总市值",
            "市盈率",
            "代码",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["开盘价"] = pd.to_numeric(temp_df["开盘价"], errors="coerce")
    temp_df["最高价"] = pd.to_numeric(temp_df["最高价"], errors="coerce")
    temp_df["最低价"] = pd.to_numeric(temp_df["最低价"], errors="coerce")
    temp_df["昨收价"] = pd.to_numeric(temp_df["昨收价"], errors="coerce")
    temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
    temp_df["市盈率"] = pd.to_numeric(temp_df["市盈率"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    for item in {
        "科技类",
        "金融类",
        "医药食品类",
        "媒体类",
        "汽车能源类",
        "制造零售类",
    }:
        stock_us_famous_spot_em_df = stock_us_famous_spot_em(symbol=item)
        print(stock_us_famous_spot_em_df)
