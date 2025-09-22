# !/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/5/16 19:00
Desc: 雪球-个股-公司概况-公司简介
https://xueqiu.com/snowman/S/SH601127/detail#/GSJJ
"""

import pandas as pd
import requests

from akshare.utils.cons import headers


def stock_individual_basic_info_xq(
    symbol: str = "SH601127", token: str = None, timeout: float = None
) -> pd.DataFrame:
    """
    雪球-个股-公司概况-公司简介
    https://xueqiu.com/snowman/S/SH601127/detail#/GSJJ
    :param symbol: 证券代码
    :type symbol: str
    :param token: 雪球财经的 token
    :type token: str
    :param timeout: 设置超时时间
    :type timeout: float
    :return: 公司简介
    :rtype: pandas.DataFrame
    """
    from akshare.stock.cons import xq_a_token
    xq_a_token = token or xq_a_token
    url = "https://stock.xueqiu.com/v5/stock/f10/cn/company.json"
    params = {
        "symbol": symbol,
    }
    headers.update({"cookie": f"xq_a_token={xq_a_token};"})
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["item", "value"]
    return temp_df


def stock_individual_basic_info_us_xq(
    symbol: str = "NVDA", token: str = None, timeout: float = None
) -> pd.DataFrame:
    """
    雪球-个股-公司概况-公司简介
    https://xueqiu.com/snowman/S/NVDA/detail#/GSJJ
    :param symbol: 证券代码
    :type symbol: str
    :param token: 雪球财经的 token
    :type token: str
    :param timeout: 设置超时时间
    :type timeout: float
    :return: 公司简介
    :rtype: pandas.DataFrame
    """
    from akshare.stock.cons import xq_a_token
    xq_a_token = token or xq_a_token
    url = "https://stock.xueqiu.com/v5/stock/f10/us/company.json"
    params = {
        "symbol": symbol,
    }
    headers.update({"cookie": f"xq_a_token={xq_a_token};"})
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["item", "value"]
    return temp_df


def stock_individual_basic_info_hk_xq(
    symbol: str = "02097", token: str = None, timeout: float = None
) -> pd.DataFrame:
    """
    雪球-个股-公司概况-公司简介
    https://xueqiu.com/S/00700
    :param symbol: 证券代码
    :type symbol: str
    :param token: 雪球财经的 token
    :type token: str
    :param timeout: 设置超时时间
    :type timeout: float
    :return: 公司简介
    :rtype: pandas.DataFrame
    """
    from akshare.stock.cons import xq_a_token
    xq_a_token = token or xq_a_token
    url = "https://stock.xueqiu.com/v5/stock/f10/hk/company.json"
    params = {
        "symbol": symbol,
    }
    headers.update({"cookie": f"xq_a_token={xq_a_token};"})
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["item", "value"]
    return temp_df


if __name__ == "__main__":
    stock_individual_basic_info_xq_df = stock_individual_basic_info_xq(
        symbol="SH601127"
    )
    print(stock_individual_basic_info_xq_df)

    stock_us_individual_basic_info_us_xq_df = stock_individual_basic_info_us_xq(
        symbol="NVDA"
    )
    print(stock_us_individual_basic_info_us_xq_df)

    stock_individual_basic_info_hk_xq_df = stock_individual_basic_info_hk_xq(
        symbol="02097"
    )
    print(stock_individual_basic_info_hk_xq_df)
