#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/6/14 17:00
Desc: 深圳证券交易所-融资融券数据
https://www.szse.cn/disclosure/margin/object/index.html
"""

import warnings

import pandas as pd
import requests


def stock_margin_underlying_info_szse(date: str = "20221129") -> pd.DataFrame:
    """
    深圳证券交易所-融资融券数据-标的证券信息
    https://www.szse.cn/disclosure/margin/object/index.html
    :param date: 交易日
    :type date: str
    :return: 标的证券信息
    :rtype: pandas.DataFrame
    """
    url = "https://www.szse.cn/api/report/ShowReport"
    params = {
        "SHOWTYPE": "xlsx",
        "CATALOGID": "1834_xxpl",
        "txtDate": "-".join([date[:4], date[4:6], date[6:]]),
        "tab1PAGENO": "1",
        "random": "0.7425245522795993",
        "TABKEY": "tab1",
    }
    headers = {
        "Referer": "https://www.szse.cn/disclosure/margin/object/index.html",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/88.0.4324.150 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        temp_df = pd.read_excel(r.content, engine="openpyxl", dtype={"证券代码": str})
    return temp_df


def stock_margin_szse(date: str = "20240411") -> pd.DataFrame:
    """
    深圳证券交易所-融资融券数据-融资融券汇总
    https://www.szse.cn/disclosure/margin/margin/index.html
    :param date: 交易日
    :type date: str
    :return: 融资融券汇总
    :rtype: pandas.DataFrame
    """
    url = "https://www.szse.cn/api/report/ShowReport/data"
    params = {
        "SHOWTYPE": "JSON",
        "CATALOGID": "1837_xxpl",
        "txtDate": "-".join([date[:4], date[4:6], date[6:]]),
        "tab1PAGENO": "1",
        "random": "0.7425245522795993",
    }
    headers = {
        "Referer": "https://www.szse.cn/disclosure/margin/object/index.html",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/88.0.4324.150 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json[0]["data"])
    temp_df.columns = [
        "融资买入额",
        "融资余额",
        "融券卖出量",
        "融券余量",
        "融券余额",
        "融资融券余额",
    ]
    temp_df["融资买入额"] = temp_df["融资买入额"].str.replace(",", "")
    temp_df["融资买入额"] = pd.to_numeric(temp_df["融资买入额"], errors="coerce")
    temp_df["融资余额"] = temp_df["融资余额"].str.replace(",", "")
    temp_df["融资余额"] = pd.to_numeric(temp_df["融资余额"], errors="coerce")
    temp_df["融券卖出量"] = temp_df["融券卖出量"].str.replace(",", "")
    temp_df["融券卖出量"] = pd.to_numeric(temp_df["融券卖出量"], errors="coerce")
    temp_df["融券余量"] = temp_df["融券余量"].str.replace(",", "")
    temp_df["融券余量"] = pd.to_numeric(temp_df["融券余量"], errors="coerce")
    temp_df["融券余额"] = temp_df["融券余额"].str.replace(",", "")
    temp_df["融券余额"] = pd.to_numeric(temp_df["融券余额"], errors="coerce")
    temp_df["融资融券余额"] = temp_df["融资融券余额"].str.replace(",", "")
    temp_df["融资融券余额"] = pd.to_numeric(temp_df["融资融券余额"], errors="coerce")
    return temp_df


def stock_margin_detail_szse(date: str = "20230925") -> pd.DataFrame:
    """
    深证证券交易所-融资融券数据-融资融券交易明细
    https://www.szse.cn/disclosure/margin/margin/index.html
    :param date: 交易日期
    :type date: str
    :return: 融资融券明细
    :rtype: pandas.DataFrame
    """
    url = "https://www.szse.cn/api/report/ShowReport"
    params = {
        "SHOWTYPE": "xlsx",
        "CATALOGID": "1837_xxpl",
        "txtDate": "-".join([date[:4], date[4:6], date[6:]]),
        "tab2PAGENO": "1",
        "random": "0.24279342734085696",
        "TABKEY": "tab2",
    }
    headers = {
        "Referer": "https://www.szse.cn/disclosure/margin/margin/index.html",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/88.0.4324.150 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        temp_df = pd.read_excel(r.content, engine="openpyxl", dtype={"证券代码": str})
    temp_df.columns = [
        "证券代码",
        "证券简称",
        "融资买入额",
        "融资余额",
        "融券卖出量",
        "融券余量",
        "融券余额",
        "融资融券余额",
    ]
    temp_df["证券简称"] = temp_df["证券简称"].str.replace("&nbsp;", "")
    temp_df["融资买入额"] = temp_df["融资买入额"].str.replace(",", "")
    temp_df["融资买入额"] = pd.to_numeric(temp_df["融资买入额"], errors="coerce")
    temp_df["融资余额"] = temp_df["融资余额"].str.replace(",", "")
    temp_df["融资余额"] = pd.to_numeric(temp_df["融资余额"], errors="coerce")
    temp_df["融券卖出量"] = temp_df["融券卖出量"].astype(str).str.replace(",", "")
    temp_df["融券卖出量"] = pd.to_numeric(temp_df["融券卖出量"], errors="coerce")
    temp_df["融券余量"] = temp_df["融券余量"].str.replace(",", "")
    temp_df["融券余量"] = pd.to_numeric(temp_df["融券余量"], errors="coerce")
    temp_df["融券余额"] = temp_df["融券余额"].str.replace(",", "")
    temp_df["融券余额"] = pd.to_numeric(temp_df["融券余额"], errors="coerce")
    temp_df["融资融券余额"] = temp_df["融资融券余额"].str.replace(",", "")
    temp_df["融资融券余额"] = pd.to_numeric(temp_df["融资融券余额"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_margin_underlying_info_szse_df = stock_margin_underlying_info_szse(
        date="20221129"
    )
    print(stock_margin_underlying_info_szse_df)

    stock_margin_szse_df = stock_margin_szse(date="20240411")
    print(stock_margin_szse_df)

    stock_margin_detail_szse_df = stock_margin_detail_szse(date="20240411")
    print(stock_margin_detail_szse_df)
