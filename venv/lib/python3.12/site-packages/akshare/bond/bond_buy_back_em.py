#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/4/5 17:30
Desc: 东方财富网-行情中心-债券市场-质押式回购
https://quote.eastmoney.com/center/gridlist.html#bond_sz_buyback
"""

import pandas as pd

import requests


def bond_sh_buy_back_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-债券市场-上证质押式回购
    https://quote.eastmoney.com/center/gridlist.html#bond_sh_buyback
    :return: 上证质押式回购
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "np": "1",
        "fltt": "1",
        "invt": "2",
        "fs": "m:1+b:MK0356",
        "fields": "f12,f13,f14,f1,f2,f4,f3,f152,f17,f18,f15,f16,f5,f6",
        "fid": "f6",
        "pn": "1",
        "pz": "20",
        "po": "1",
        "dect": "1",
        "wbp2u": "|0|0|0|web",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json['data']['diff'])
    temp_df.reset_index(inplace=True)
    temp_df['index'] = temp_df['index'] + 1
    temp_df.rename(
        columns={
            "index": "序号",
            "f2": "最新价",
            "f3": "涨跌幅",
            "f4": "涨跌额",
            "f5": "成交量",
            "f6": "成交额",
            "f12": "代码",
            "f14": "名称",
            "f15": "最高",
            "f16": "最低",
            "f17": "今开",
            "f18": "昨收",
        },
        inplace=True,
    )

    temp_df = temp_df[[
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
    ]]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce") / 1000
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce") / 100
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce") / 1000
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce") / 1000
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce") / 1000
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce") / 1000
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce") / 1000
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    return temp_df


def bond_sz_buy_back_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-债券市场-深证质押式回购
    https://quote.eastmoney.com/center/gridlist.html#bond_sz_buyback
    :return: 深证质押式回购
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "np": "1",
        "fltt": "1",
        "invt": "2",
        "fs": "m:0+b:MK0356",
        "fields": "f12,f13,f14,f1,f2,f4,f3,f152,f17,f18,f15,f16,f5,f6",
        "fid": "f6",
        "pn": "1",
        "pz": "20",
        "po": "1",
        "dect": "1",
        "wbp2u": "|0|0|0|web",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json['data']['diff'])
    temp_df.reset_index(inplace=True)
    temp_df['index'] = temp_df['index'] + 1
    temp_df.rename(
        columns={
            "index": "序号",
            "f2": "最新价",
            "f3": "涨跌幅",
            "f4": "涨跌额",
            "f5": "成交量",
            "f6": "成交额",
            "f12": "代码",
            "f14": "名称",
            "f15": "最高",
            "f16": "最低",
            "f17": "今开",
            "f18": "昨收",
        },
        inplace=True,
    )

    temp_df = temp_df[[
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
    ]]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce") / 1000
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce") / 100
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce") / 1000
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce") / 1000
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce") / 1000
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce") / 1000
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce") / 1000
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    return temp_df


def bond_buy_back_hist_em(symbol: str = "204001"):
    """
    东方财富网-行情中心-债券市场-质押式回购-历史数据
    https://quote.eastmoney.com/center/gridlist.html#bond_sh_buyback
    :param symbol: 质押式回购代码
    :type symbol: str
    :return: 历史数据
    :rtype: pandas.DataFrame
    """
    if symbol.startswith("1"):
        market_id = "0"
    else:
        market_id = "1"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": f"{market_id}.{symbol}",
        "klt": "101",
        "fqt": "1",
        "lmt": "10000",
        "end": "20500000",
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
        "forcect": "1"
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(',') for item in data_json['data']['klines']])
    temp_df.columns = [
            "日期",
            "开盘",
            "收盘",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
    ]
    temp_df = temp_df[[
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
    ]]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["开盘"] = pd.to_numeric(temp_df["开盘"], errors="coerce")
    temp_df["收盘"] = pd.to_numeric(temp_df["收盘"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    bond_sh_buy_back_em_df = bond_sh_buy_back_em()
    print(bond_sh_buy_back_em_df)

    bond_sz_buy_back_em_df = bond_sz_buy_back_em()
    print(bond_sz_buy_back_em_df)

    bond_buy_back_hist_em_df = bond_buy_back_hist_em(symbol="204001")
    print(bond_buy_back_hist_em_df)

    bond_buy_back_hist_em_df = bond_buy_back_hist_em(symbol="131810")
    print(bond_buy_back_hist_em_df)
