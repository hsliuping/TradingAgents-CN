#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/2/20 17:00
Desc: 东方财富网-期货行情
https://qhweb.eastmoney.com/quote
"""

import re
from functools import lru_cache
from typing import Tuple, Dict

import pandas as pd
import requests


def __futures_hist_separate_char_and_numbers_em(symbol: str = "焦煤2506") -> tuple:
    """
    东方财富网-期货行情-交易所品种对照表原始数据
    https://quote.eastmoney.com/qihuo/al2505.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 交易所品种对照表原始数据
    :rtype: pandas.DataFrame
    """
    char = re.findall(pattern="[\u4e00-\u9fa5a-zA-Z]+", string=symbol)
    numbers = re.findall(pattern=r"\d+", string=symbol)
    return char[0], numbers[0]


@lru_cache()
def __fetch_exchange_symbol_raw_em() -> list:
    """
    东方财富网-期货行情-交易所品种对照表原始数据
    https://quote.eastmoney.com/qihuo/al2505.html
    :return: 交易所品种对照表原始数据
    :rtype: pandas.DataFrame
    """
    url = "https://futsse-static.eastmoney.com/redis"
    params = {"msgid": "gnweb"}
    r = requests.get(url, params=params)
    data_json = r.json()
    all_exchange_symbol_list = []
    for item in data_json:
        params = {"msgid": str(item["mktid"])}
        r = requests.get(url, params=params)
        inner_data_json = r.json()
        for num in range(1, len(inner_data_json) + 1):
            params = {"msgid": str(item["mktid"]) + f"_{num}"}
            r = requests.get(url, params=params)
            inner_data_json = r.json()
            all_exchange_symbol_list.extend(inner_data_json)
    return all_exchange_symbol_list


@lru_cache()
def __get_exchange_symbol_map() -> Tuple[Dict, Dict, Dict, Dict]:
    """
    东方财富网-期货行情-交易所品种映射
    https://quote.eastmoney.com/qihuo/al2505.html
    :return: 交易所品种映射
    :rtype: pandas.DataFrame
    """
    all_exchange_symbol_list = __fetch_exchange_symbol_raw_em()
    c_contract_mkt = {}
    c_contract_to_e_contract = {}
    e_symbol_mkt = {}
    c_symbol_mkt = {}
    for item in all_exchange_symbol_list:
        c_contract_mkt[item["name"]] = item["mktid"]
        c_contract_to_e_contract[item["name"]] = item["code"]
        e_symbol_mkt[item["vcode"]] = item["mktid"]
        c_symbol_mkt[item["vname"]] = item["mktid"]
    return c_contract_mkt, c_contract_to_e_contract, e_symbol_mkt, c_symbol_mkt


def futures_hist_table_em() -> pd.DataFrame:
    """
    东方财富网-期货行情-交易所品种对照表
    https://quote.eastmoney.com/qihuo/al2505.html
    :return: 交易所品种对照表
    :rtype: pandas.DataFrame
    """
    all_exchange_symbol_list = __fetch_exchange_symbol_raw_em()
    temp_df = pd.DataFrame(all_exchange_symbol_list)
    temp_df = temp_df[["mktname", "name", "code"]]
    temp_df.columns = ["市场简称", "合约中文代码", "合约代码"]
    return temp_df


def futures_hist_em(
    symbol: str = "热卷主连",
    period: str = "daily",
    start_date: str = "19900101",
    end_date: str = "20500101",
) -> pd.DataFrame:
    """
    东方财富网-期货行情-行情数据
    https://qhweb.eastmoney.com/quote
    :param symbol: 期货代码
    :type symbol: str
    :param period: choice of {'daily', 'weekly', 'monthly'}
    :type period: str
    :param start_date: 开始日期
    :type start_date: str
    :param end_date: 结束日期
    :type end_date: str
    :return: 行情数据
    :rtype: pandas.DataFrame
    """
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    period_dict = {"daily": "101", "weekly": "102", "monthly": "103"}
    c_contract_mkt, c_contract_to_e_contract, e_symbol_mkt, c_symbol_mkt = (
        __get_exchange_symbol_map()
    )
    try:
        sec_id = f"{c_contract_mkt[symbol]}.{c_contract_to_e_contract[symbol]}"
    except KeyError:
        symbol_char, numbers = __futures_hist_separate_char_and_numbers_em(symbol)
        if re.match(pattern="^[\u4e00-\u9fa5]+$", string=symbol_char):
            sec_id = str(c_symbol_mkt[symbol_char]) + "." + symbol
        else:
            sec_id = str(e_symbol_mkt[symbol_char]) + "." + symbol
    params = {
        "secid": sec_id,
        "klt": period_dict[period],
        "fqt": "1",
        "lmt": "10000",
        "end": "20500000",
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "forcect": "1",
    }
    r = requests.get(url, timeout=15, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    temp_df.columns = [
        "时间",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "-",
        "涨跌幅",
        "涨跌",
        "_",
        "_",
        "持仓量",
        "_",
    ]
    temp_df = temp_df[
        [
            "时间",
            "开盘",
            "最高",
            "最低",
            "收盘",
            "涨跌",
            "涨跌幅",
            "成交量",
            "成交额",
            "持仓量",
        ]
    ]
    temp_df.index = pd.to_datetime(temp_df["时间"])
    temp_df = temp_df[start_date:end_date]
    temp_df.reset_index(drop=True, inplace=True)
    temp_df["开盘"] = pd.to_numeric(temp_df["开盘"], errors="coerce")
    temp_df["收盘"] = pd.to_numeric(temp_df["收盘"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["涨跌"] = pd.to_numeric(temp_df["涨跌"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["持仓量"] = pd.to_numeric(temp_df["持仓量"], errors="coerce")
    temp_df["时间"] = pd.to_datetime(temp_df["时间"], errors="coerce").dt.date
    return temp_df


if __name__ == "__main__":
    futures_hist_table_em_df = futures_hist_table_em()
    print(futures_hist_table_em_df)

    futures_hist_em_df = futures_hist_em(symbol="热卷主连", period="daily")
    print(futures_hist_em_df)
