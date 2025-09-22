#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/7/1 16:30
Desc: 期货-仓单日报
上海期货交易所-仓单日报
https://tsite.shfe.com.cn/statements/dataview.html?paramid=dailystock
郑州商品交易所-交易数据-仓单日报
http://www.czce.com.cn/cn/jysj/cdrb/H770310index_1.htm
大连商品交易所-行情数据-统计数据-日统计-仓单日报
http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/cdrb/index.html
广州期货交易所-行情数据-仓单日报
http://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml
"""

import re
from io import BytesIO, StringIO

import pandas as pd
import requests


def futures_czce_warehouse_receipt(date: str = "20200702") -> dict:
    """
    郑州商品交易所-交易数据-仓单日报
    http://www.czce.com.cn/cn/jysj/cdrb/H770310index_1.htm
    :param date: 交易日, e.g., "20200702"
    :type date: str
    :return: 指定日期的仓单日报数据
    :rtype: dict
    """
    url = f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{date[:4]}/{date}/FutureDataWhsheet.xls"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/83.0.4103.116 Safari/537.36"
    }
    r = requests.get(url, verify=False, headers=headers)
    temp_df = pd.read_excel(BytesIO(r.content))
    index_list = temp_df[temp_df.iloc[:, 0].str.find("品种") == 0.0].index.to_list()
    index_list.append(len(temp_df))
    big_dict = {}
    for inner_index in range(len(index_list) - 1):
        inner_df = temp_df[index_list[inner_index] : index_list[inner_index + 1]]
        inner_key = re.findall(r"[a-zA-Z]+", inner_df.iloc[0, 0])[0]
        inner_df = inner_df.iloc[1:, :]
        inner_df.dropna(axis=0, how="all", inplace=True)
        inner_df.dropna(axis=1, how="all", inplace=True)
        inner_df.columns = inner_df.iloc[0, :].to_list()
        inner_df = inner_df.iloc[1:, :]
        inner_df.reset_index(inplace=True, drop=True)
        big_dict[inner_key] = inner_df
    return big_dict


def futures_dce_warehouse_receipt(date: str = "20200702") -> dict:
    """
    大连商品交易所-行情数据-统计数据-日统计-仓单日报
    http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/cdrb/index.html
    :param date: 交易日, e.g., "20200702"
    :type date: str
    :return: 指定日期的仓单日报数据
    :rtype: dict
    """
    url = "http://www.dce.com.cn/publicweb/quotesdata/wbillWeeklyQuotes.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/83.0.4103.116 Safari/537.36"
    }
    params = {
        "wbillWeeklyQuotes.variety": "all",
        "year": date[:4],
        "month": str(int(date[4:6]) - 1),
        "day": date[6:],
    }
    r = requests.get(url, params=params, headers=headers)
    temp_df = pd.read_html(StringIO(r.text))[0]
    index_list = temp_df[temp_df.iloc[:, 0].str.contains("小计") == 1].index.to_list()
    index_list.insert(0, 0)
    big_dict = {}
    for inner_index in range(len(index_list) - 1):
        if inner_index == 0:
            temp_index = 0
        else:
            temp_index = index_list[inner_index] + 1
        inner_df = temp_df[temp_index : index_list[inner_index + 1] + 1].copy()
        inner_key = inner_df.iloc[0, 0]
        inner_df.reset_index(inplace=True, drop=True)
        inner_df.ffill(inplace=True)
        # 填补 20240401 中开头没有品种的情况
        if date == "20240401":
            inner_df["品种"] = inner_df["品种"].fillna("玉米")
            inner_key = inner_df.iloc[0, 0]
        big_dict[inner_key] = inner_df
    return big_dict


def futures_shfe_warehouse_receipt(date: str = "20200702") -> dict:
    """
    上海期货交易所指定交割仓库期货仓单日报
    https://tsite.shfe.com.cn/statements/dataview.html?paramid=dailystock&paramdate=20200703
    :param date: 交易日, e.g., "20200702"
    :type date: str
    :return: 指定日期的仓单日报数据
    :rtype: dict
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/83.0.4103.116 Safari/537.36"
    }
    url = f"https://www.shfe.com.cn/data/tradedata/future/dailydata/{date}dailystock.dat"
    if date >= "20140519":
        r = requests.get(url, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["o_cursor"])
        temp_df["VARNAME"] = temp_df["VARNAME"].str.split(r"$", expand=True).iloc[:, 0]
        temp_df["REGNAME"] = temp_df["REGNAME"].str.split(r"$", expand=True).iloc[:, 0]
        temp_df["WHABBRNAME"] = (
            temp_df["WHABBRNAME"].str.split(r"$", expand=True).iloc[:, 0]
        )
        big_dict = {}
        for item in set(temp_df["VARNAME"]):
            big_dict[item] = temp_df[temp_df["VARNAME"] == item]
    else:
        url = f"https://www.shfe.com.cn/data/tradedata/future/dailydata/{date}dailystock.html"
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text))[0]
        index_list = temp_df[
            temp_df.iloc[:, 3].str.contains("单位：") == 1
        ].index.to_list()
        big_dict = {}
        for inner_index in range(len(index_list)):
            temp_index_start = index_list[inner_index]
            if (inner_index + 1) >= len(index_list):
                if temp_df.iloc[-1, 0].startswith("注："):
                    temp_index_end = len(temp_df) - 1
                else:
                    temp_index_end = len(temp_df)
            else:
                temp_index_end = index_list[inner_index + 1]
            inner_df = temp_df[temp_index_start:temp_index_end]
            inner_df.reset_index(inplace=True, drop=True)
            inner_key = inner_df.iloc[0, 0]
            inner_df.columns = inner_df.iloc[1].to_list()
            inner_df = inner_df[2:]
            inner_df.reset_index(inplace=True, drop=True)
            big_dict[inner_key] = inner_df
    return big_dict


def futures_gfex_warehouse_receipt(date: str = "20240122") -> dict:
    """
    广州期货交易所-行情数据-仓单日报
    http://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml
    :param date: 交易日, e.g., "20240122"
    :type date: str
    :return: 指定日期的仓单日报数据
    :rtype: dict
    """
    url = "http://www.gfex.com.cn/u/interfacesWebTdWbillWeeklyQuotes/loadList"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/83.0.4103.116 Safari/537.36"
    }
    payload = {"gen_date": date}
    r = requests.post(url=url, data=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    symbol_list = list(
        set([item.upper() for item in temp_df["varietyOrder"].tolist() if item != ""])
    )
    temp_df.rename(
        columns={
            "varietyOrder": "symbol",
            "variety": "品种",
            "whAbbr": "仓库/分库",
            "lastWbillQty": "昨日仓单量",
            "wbillQty": "今日仓单量",
            "regWbillQty": "增减",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "symbol",
            "whType",
            "品种",
            "仓库/分库",
            "昨日仓单量",
            "今日仓单量",
            "增减",
        ]
    ]
    temp_df["whType"] = pd.to_numeric(temp_df["whType"], errors="coerce")
    temp_df.dropna(
        subset=["whType"], how="any", axis=0, ignore_index=True, inplace=True
    )
    big_dict = dict()
    for symbol in symbol_list:
        inner_temp_df = temp_df[temp_df["symbol"] == symbol.lower()].copy()
        inner_temp_df = inner_temp_df[
            [
                "品种",
                "仓库/分库",
                "昨日仓单量",
                "今日仓单量",
                "增减",
            ]
        ]
        inner_temp_df["昨日仓单量"] = pd.to_numeric(
            inner_temp_df["昨日仓单量"], errors="coerce"
        )
        inner_temp_df["今日仓单量"] = pd.to_numeric(
            inner_temp_df["今日仓单量"], errors="coerce"
        )
        inner_temp_df["增减"] = pd.to_numeric(inner_temp_df["增减"], errors="coerce")
        inner_temp_df.reset_index(inplace=True, drop=True)
        big_dict[symbol] = inner_temp_df
    return big_dict


if __name__ == "__main__":
    czce_warehouse_receipt_df = futures_czce_warehouse_receipt(date="20151019")
    print(czce_warehouse_receipt_df)

    futures_dce_warehouse_receipt_df = futures_dce_warehouse_receipt(date="20240401")
    print(futures_dce_warehouse_receipt_df)

    futures_shfe_warehouse_receipt_df = futures_shfe_warehouse_receipt(date="20200702")
    print(futures_shfe_warehouse_receipt_df)

    futures_shfe_warehouse_receipt_df = futures_shfe_warehouse_receipt(date="20140516")
    print(futures_shfe_warehouse_receipt_df)

    futures_gfex_warehouse_receipt_df = futures_gfex_warehouse_receipt(date="20240122")
    print(futures_gfex_warehouse_receipt_df)
