#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/1/29 17:00
Desc: 查询期货合约当前时刻的详情
https://finance.sina.com.cn/futures/quotes/V2101.shtml
"""

from io import StringIO

import pandas as pd
import requests


def futures_contract_detail(symbol: str = "AP2101") -> pd.DataFrame:
    """
    查询期货合约详情
    https://finance.sina.com.cn/futures/quotes/V2101.shtml
    :param symbol: 合约
    :type symbol: str
    :return: 期货合约详情
    :rtype: pandas.DataFrame
    """
    url = f"https://finance.sina.com.cn/futures/quotes/{symbol}.shtml"
    r = requests.get(url)
    r.encoding = "gb2312"
    temp_df = pd.read_html(StringIO(r.text))[6]
    data_one = temp_df.iloc[:, :2]
    data_one.columns = ["item", "value"]
    data_two = temp_df.iloc[:, 2:4]
    data_two.columns = ["item", "value"]
    data_three = temp_df.iloc[:, 4:]
    data_three.columns = ["item", "value"]
    temp_df = pd.concat(
        objs=[data_one, data_two, data_three], axis=0, ignore_index=True
    )
    return temp_df


if __name__ == "__main__":
    futures_contract_detail_df = futures_contract_detail(symbol="IM2402")
    print(futures_contract_detail_df)
