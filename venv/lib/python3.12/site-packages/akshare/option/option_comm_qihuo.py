#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/7/5 15:00
Desc: 九期网-商品期权手续费
https://www.9qihuo.com/qiquanshouxufei
"""

from functools import lru_cache
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup


@lru_cache()
def option_comm_symbol() -> pd.DataFrame:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    url = "https://www.9qihuo.com/qiquanshouxufei"
    r = requests.get(url, verify=False)
    soup = BeautifulSoup(r.text, features="lxml")
    name = [
        item.string.strip()
        for item in soup.find(name="div", attrs={"id": "inst_list"}).find_all(name="a")
    ]
    code = [
        item["href"].split("?")[1].split("=")[1]
        for item in soup.find(name="div", attrs={"id": "inst_list"}).find_all(name="a")
    ]
    temp_df = pd.DataFrame([name, code]).T
    temp_df.columns = ["品种名称", "品种代码"]
    return temp_df


def option_comm_info(symbol: str = "工业硅期权") -> pd.DataFrame:
    """
    九期网-商品期权手续费
    https://www.9qihuo.com/qiquanshouxufei
    :param symbol: choice of {"所有", "上海期货交易所", "大连商品交易所", "郑州商品交易所", "上海国际能源交易中心", "广州期货交易所"}
    :type symbol: str
    :return: 期权手续费
    :rtype: pandas.DataFrame
    """
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    symbol_df = option_comm_symbol()
    symbol_str = symbol_df[symbol_df["品种名称"].str.contains(symbol)][
        "品种代码"
    ].values[0]
    params = {"heyue": symbol_str}
    url = "https://www.9qihuo.com/qiquanshouxufei"
    r = requests.get(url, params=params, verify=False)
    temp_df = pd.read_html(StringIO(r.text))[0]
    market_symbol = temp_df.iloc[0, 0]
    columns = temp_df.iloc[2, :]
    temp_df = temp_df.iloc[3:, :]
    temp_df.columns = columns
    temp_df["交易所"] = market_symbol
    temp_df.reset_index(drop=True, inplace=True)
    temp_df.index.name = None
    temp_df.columns.name = None
    temp_df["现价"] = pd.to_numeric(temp_df["现价"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["每跳毛利/元"] = pd.to_numeric(temp_df["每跳毛利/元"], errors="coerce")
    temp_df["每跳净利/元"] = pd.to_numeric(temp_df["每跳净利/元"], errors="coerce")
    soup = BeautifulSoup(r.text, features="lxml")
    raw_date_text = soup.find(name="a", attrs={"id": "dlink"}).previous
    comm_update_time = raw_date_text.split("，")[0].strip("（手续费更新时间：")
    price_update_time = (
        raw_date_text.split("，")[1].strip("价格更新时间：").strip("。）")
    )
    temp_df["手续费更新时间"] = comm_update_time
    temp_df["价格更新时间"] = price_update_time
    return temp_df


if __name__ == "__main__":
    option_comm_symbol_df = option_comm_symbol()
    print(option_comm_symbol_df)

    option_comm_info_df = option_comm_info(symbol="工业硅期权")
    print(option_comm_info_df)
