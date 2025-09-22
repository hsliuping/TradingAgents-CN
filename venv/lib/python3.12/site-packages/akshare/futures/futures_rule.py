#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/31 18:00
Desc: 国泰君安期货-交易日历数据表
https://www.gtjaqh.com/pc/calendar.html
"""

from io import StringIO

import pandas as pd
import requests


def futures_rule(date: str = "20231205") -> pd.DataFrame:
    """
    国泰君安期货-交易日历数据表
    https://www.gtjaqh.com/pc/calendar.html
    :param date: 需要指定为交易日, 且是近期的日期
    :type date: str
    :return: 交易日历数据
    :rtype: pandas.DataFrame
    """
    import urllib3

    urllib3.disable_warnings()
    url = " https://www.gtjaqh.com/pc/calendar"
    params = {"date": f"{date}"}
    r = requests.get(url, params=params, verify=False)
    big_df = pd.read_html(StringIO(r.text), header=1)[0]
    big_df["交易保证金比例"] = big_df["交易保证金比例"].str.strip("%")
    big_df["交易保证金比例"] = pd.to_numeric(big_df["交易保证金比例"], errors="coerce")
    big_df["涨跌停板幅度"] = big_df["涨跌停板幅度"].str.strip("%")
    big_df["涨跌停板幅度"] = pd.to_numeric(big_df["涨跌停板幅度"], errors="coerce")
    big_df["合约乘数"] = pd.to_numeric(big_df["合约乘数"], errors="coerce")
    big_df["最小变动价位"] = pd.to_numeric(big_df["最小变动价位"], errors="coerce")
    big_df["限价单每笔最大下单手数"] = pd.to_numeric(
        big_df["限价单每笔最大下单手数"], errors="coerce"
    )
    return big_df


if __name__ == "__main__":
    futures_rule_df = futures_rule(date="20250328")
    print(futures_rule_df)
