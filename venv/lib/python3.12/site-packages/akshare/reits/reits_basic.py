#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/27 15:00
Desc: REITs 行情及信息
https://quote.eastmoney.com/center/gridlist.html#fund_reits_all
https://www.jisilu.cn/data/cnreits/#CnReits
"""

import pandas as pd
import requests
from functools import lru_cache
from typing import Dict


@lru_cache()
def __reits_code_market_map() -> Dict:
    """
    东方财富网-行情中心-REITs-沪深 REITs
    https://quote.eastmoney.com/center/gridlist.html#fund_reits_all
    :return: 沪深 REITs-实时行情
    :rtype: pandas.DataFrame
    """
    url = "https://95.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:1 t:9 e:97,m:0 t:10 e:97",
        "fields": "f12,f13",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["diff"])
    temp_dict = dict(zip(temp_df["f12"], temp_df["f13"]))
    return temp_dict


def reits_realtime_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-REITs-沪深 REITs
    https://quote.eastmoney.com/center/gridlist.html#fund_reits_all
    :return: 沪深 REITs-实时行情
    :rtype: pandas.DataFrame
    """
    url = "https://95.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:1 t:9 e:97,m:0 t:10 e:97",
        "fields": "f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["diff"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = range(1, len(temp_df) + 1)
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
            "f15": "最高价",
            "f16": "最低价",
            "f17": "开盘价",
            "f18": "昨收",
            "f13": "市场标识",
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
            "成交量",
            "成交额",
            "开盘价",
            "最高价",
            "最低价",
            "昨收",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["开盘价"] = pd.to_numeric(temp_df["开盘价"], errors="coerce")
    temp_df["最高价"] = pd.to_numeric(temp_df["最高价"], errors="coerce")
    temp_df["最低价"] = pd.to_numeric(temp_df["最低价"], errors="coerce")
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce")
    return temp_df


def reits_hist_em(symbol: str = "508097") -> pd.DataFrame:
    """
    东方财富网-行情中心-REITs-沪深 REITs-历史行情
    https://quote.eastmoney.com/sh508097.html
    :param symbol: REITs 代码
    :type symbol: str
    :return: 沪深 REITs-历史行情
    :rtype: pandas.DataFrame
    """
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    code_market_dict = __reits_code_market_map()
    params = {
        "secid": f"{code_market_dict[symbol]}.{symbol}",
        "klt": "101",
        "fqt": "1",
        "lmt": "10000",
        "end": "20500000",
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "forcect": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    temp_df.columns = [
        "日期",
        "今开",
        "最新价",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "振幅",
        "-",
        "-",
        "换手",
        "-",
        "-",
        "-",
    ]
    temp_df = temp_df[
        ["日期", "今开", "最高", "最低", "最新价", "成交量", "成交额", "振幅", "换手"]
    ]
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
    temp_df["换手"] = pd.to_numeric(temp_df["换手"], errors="coerce")
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    return temp_df


def reits_hist_min_em(symbol: str = "508097") -> pd.DataFrame:
    """
    东方财富网-行情中心-REITs-沪深 REITs-历史行情
    https://quote.eastmoney.com/sh508097.html
    :param symbol: REITs 代码
    :type symbol: str
    :return: 沪深 REITs-历史行情
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/stock/trends2/get"
    code_market_dict = __reits_code_market_map()
    params = {
        "secid": f"{code_market_dict[symbol]}.{symbol}",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f17",
        "fields2": "f51,f53,f54,f55,f56,f57,f58",
        "iscr": "0",
        "iscca": "0",
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "ndays": "5",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["trends"]])
    temp_df.columns = [
        "时间",
        "最新价",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "昨收",
    ]

    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    reits_realtime_em_df = reits_realtime_em()
    print(reits_realtime_em_df)

    reits_hist_em_df = reits_hist_em(symbol="508097")
    print(reits_hist_em_df)

    reits_hist_min_em_df = reits_hist_min_em(symbol="508097")
    print(reits_hist_min_em_df)
