#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/9 22:00
Desc: 东方财富网-行情中心-期货市场-国际期货
https://quote.eastmoney.com/center/gridlist.html#futures_global
"""

import math
from typing import Optional

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def __futures_global_hist_market_code(symbol: str = "HG00Y") -> Optional[int]:
    """
    东方财富网-行情中心-期货市场-国际期货-品种市场对照表
    https://quote.eastmoney.com/center/gridlist.html#futures_global
    :param symbol: HG00Y, 品种代码；可以通过 ak.futures_global_spot_em() 来获取所有可获取历史行情数据的品种代码
    :type symbol: str
    :return: 品种所属于的市场
    :rtype: str
    """
    # 提取品种代码（去掉年份和月份部分）
    base_symbol = ""
    i = 0
    while i < len(symbol) and not symbol[i].isdigit():
        base_symbol += symbol[i]
        i += 1
    # 如果代码中没有数字（异常情况），则返回整个代码作为基础品种代码
    if not base_symbol and i == len(symbol):
        base_symbol = symbol
    # 金属和贵金属品种 - 101
    if base_symbol in ["HG", "GC", "SI", "QI", "QO", "MGC", "LTH"]:
        return 101
    # 能源品种 - 102
    if base_symbol in ["CL", "NG", "RB", "HO", "PA", "PL", "QM"]:
        return 102
    # 农产品和金融品种 - 103
    if base_symbol in [
        "ZW",
        "ZM",
        "ZS",
        "ZC",
        "XC",
        "XK",
        "XW",
        "YM",
        "TY",
        "US",
        "EH",
        "ZL",
        "ZR",
        "ZO",
        "FV",
        "TU",
        "UL",
        "NQ",
        "ES",
    ]:
        return 103
    # 中国市场特有品种 - 104
    if base_symbol in ["TF", "RT", "CN"]:
        return 104
    # 软商品期货 - 108
    if base_symbol in ["SB", "CT", "SF"]:
        return 108
    # 特殊L开头品种 - 109
    if base_symbol in ["LCPT", "LZNT", "LALT", "LTNT", "LLDT", "LNKT"]:
        return 109
    # MPM开头品种 - 110
    if base_symbol == "MPM":
        return 110
    # 日本市场品种 - 111
    if base_symbol.startswith("J"):
        return 111
    # 单字母代码品种 - 112
    if base_symbol in ["M", "B", "G"]:
        return 112
    # 如果没有匹配到任何规则，返回一个默认值或者错误
    return None


def futures_global_spot_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-期货市场-国际期货
    https://quote.eastmoney.com/center/gridlist.html#futures_global
    :return: 行情数据
    :rtype: pandas.DataFrame
    """
    url = "https://futsseapi.eastmoney.com/list/COMEX,NYMEX,COBOT,SGX,NYBOT,LME,MDEX,TOCOM,IPE"
    params = {
        "orderBy": "dm",
        "sort": "desc",
        "pageSize": "20",
        "pageIndex": "0",
        "token": "58b2fa8f54638b60b87d69b31969089c",
        "field": "dm,sc,name,p,zsjd,zde,zdf,f152,o,h,l,zjsj,vol,wp,np,ccl",
        "blockName": "callback",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_num = data_json["total"]
    total_page = math.ceil(total_num / 20) - 1
    tqdm = get_tqdm()
    big_df = pd.DataFrame()
    for page in tqdm(range(total_page), leave=False):
        params.update({"pageIndex": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["list"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    big_df.rename(
        columns={
            "index": "序号",
            "np": "卖盘",
            "h": "最高",
            "dm": "代码",
            "zsjd": "-",
            "l": "最低",
            "ccl": "持仓量",
            "o": "今开",
            "p": "最新价",
            "sc": "-",
            "vol": "成交量",
            "name": "名称",
            "wp": "买盘",
            "zde": "涨跌额",
            "zdf": "涨跌幅",
            "zjsj": "昨结",
        },
        inplace=True,
    )
    big_df = big_df[
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
            "昨结",
            "成交量",
            "买盘",
            "卖盘",
            "持仓量",
        ]
    ]
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["涨跌额"] = pd.to_numeric(big_df["涨跌额"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["今开"] = pd.to_numeric(big_df["今开"], errors="coerce")
    big_df["最高"] = pd.to_numeric(big_df["最高"], errors="coerce")
    big_df["最低"] = pd.to_numeric(big_df["最低"], errors="coerce")
    big_df["昨结"] = pd.to_numeric(big_df["昨结"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["买盘"] = pd.to_numeric(big_df["买盘"], errors="coerce")
    big_df["卖盘"] = pd.to_numeric(big_df["卖盘"], errors="coerce")
    big_df["持仓量"] = pd.to_numeric(big_df["持仓量"], errors="coerce")
    return big_df


def futures_global_hist_em(symbol: str = "HG00Y") -> pd.DataFrame:
    """
    东方财富网-行情中心-期货市场-国际期货-历史行情数据
    https://quote.eastmoney.com/globalfuture/HG25J.html
    :param symbol: 品种代码；可以通过 ak.futures_global_spot_em() 来获取所有可获取历史行情数据的品种代码
    :type symbol: str
    :return: 历史行情数据
    :rtype: pandas.DataFrame
    """
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    market_code = __futures_global_hist_market_code(symbol)
    params = {
        "secid": f"{market_code}.{symbol}",
        "klt": "101",
        "fqt": "1",
        "lmt": "6600",
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
    temp_df["code"] = data_json["data"]["code"]
    temp_df["name"] = data_json["data"]["name"]
    temp_df.columns = [
        "日期",
        "开盘",
        "最新价",
        "最高",
        "最低",
        "总量",
        "-",
        "-",
        "涨幅",
        "-",
        "-",
        "-",
        "持仓",
        "日增",
        "代码",
        "名称",
    ]
    temp_df = temp_df[
        [
            "日期",
            "代码",
            "名称",
            "开盘",
            "最新价",
            "最高",
            "最低",
            "总量",
            "涨幅",
            "持仓",
            "日增",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["开盘"] = pd.to_numeric(temp_df["开盘"], errors="coerce")
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["总量"] = pd.to_numeric(temp_df["总量"], errors="coerce")
    temp_df["涨幅"] = pd.to_numeric(temp_df["涨幅"], errors="coerce")
    temp_df["日增"] = pd.to_numeric(temp_df["日增"], errors="coerce")
    # 日增修复为有符号32位整数值
    unsigned_max, signed_max = (2 ** 32) - 1, (2 ** 31) - 1
    mask = temp_df["日增"] > signed_max
    temp_df.loc[mask, "日增"] = temp_df.loc[mask, "日增"] - (unsigned_max + 1)
    return temp_df


if __name__ == "__main__":
    futures_global_spot_em_df = futures_global_spot_em()
    print(futures_global_spot_em_df)

    futures_global_hist_em_df = futures_global_hist_em(symbol="HG00Y")
    print(futures_global_hist_em_df)
