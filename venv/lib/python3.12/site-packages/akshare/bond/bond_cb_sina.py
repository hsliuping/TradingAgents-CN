# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2023/9/12 16:50
Desc: 新浪财经-债券-可转债
https://money.finance.sina.com.cn/bond/info/sz128039.html
"""

from io import StringIO

import pandas as pd
import requests


def bond_cb_profile_sina(symbol: str = "sz128039") -> pd.DataFrame:
    """
    新浪财经-债券-可转债-详情资料
    https://money.finance.sina.com.cn/bond/info/sz128039.html
    :param symbol: 带市场标识的转债代码
    :type symbol: str
    :return: 可转债-详情资料
    :rtype: pandas.DataFrame
    """
    url = f"https://money.finance.sina.com.cn/bond/info/{symbol}.html"
    r = requests.get(url)
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df.columns = ["item", "value"]
    return temp_df


def bond_cb_summary_sina(symbol: str = "sh155255") -> pd.DataFrame:
    """
    新浪财经-债券-可转债-债券概况
    https://money.finance.sina.com.cn/bond/quotes/sh155255.html
    :param symbol: 带市场标识的转债代码
    :type symbol: str
    :return: 可转债-债券概况
    :rtype: pandas.DataFrame
    """
    url = f"https://money.finance.sina.com.cn/bond/quotes/{symbol}.html"
    r = requests.get(url)
    temp_df = pd.read_html(StringIO(r.text))[10]
    part1 = temp_df.iloc[:, 0:2].copy()
    part1.columns = ["item", "value"]
    part2 = temp_df.iloc[:, 2:4].copy()
    part2.columns = ["item", "value"]
    part3 = temp_df.iloc[:, 4:6].copy()
    part3.columns = ["item", "value"]
    big_df = pd.concat(objs=[part1, part2, part3], ignore_index=True)
    return big_df


if __name__ == "__main__":
    bond_cb_profile_sina_df = bond_cb_profile_sina(symbol="sz128039")
    print(bond_cb_profile_sina_df)

    bond_cb_summary_sina_df = bond_cb_summary_sina(symbol="sh155255")
    print(bond_cb_summary_sina_df)
