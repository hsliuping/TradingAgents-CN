#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/13 10:30
Desc: 同花顺-分红情况
https://basic.10jqka.com.cn/new/603444/bonus.html
"""

from io import StringIO

import pandas as pd
import requests


def stock_fhps_detail_ths(symbol: str = "603444") -> pd.DataFrame:
    """
    同花顺-分红情况
    https://basic.10jqka.com.cn/new/603444/bonus.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 分红融资
    :rtype: pandas.DataFrame
    """
    url = f"https://basic.10jqka.com.cn/new/{symbol}/bonus.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/89.0.4389.90 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    r.encoding = "gbk"
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df["董事会日期"] = pd.to_datetime(
        temp_df["董事会日期"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df["股东大会预案公告日期"] = pd.to_datetime(
        temp_df["股东大会预案公告日期"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df["实施公告日"] = pd.to_datetime(
        temp_df["实施公告日"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    if "A股股权登记日" in temp_df.columns:
        temp_df["A股股权登记日"] = pd.to_datetime(
            temp_df["A股股权登记日"], format="%Y-%m-%d", errors="coerce"
        ).dt.date
        temp_df["A股除权除息日"] = pd.to_datetime(
            temp_df["A股除权除息日"], format="%Y-%m-%d", errors="coerce"
        ).dt.date
    else:
        temp_df["B股股权登记日"] = pd.to_datetime(
            temp_df["B股股权登记日"], format="%Y-%m-%d", errors="coerce"
        ).dt.date
        temp_df["B股除权除息日"] = pd.to_datetime(
            temp_df["B股除权除息日"], format="%Y-%m-%d", errors="coerce"
        ).dt.date
    temp_df.sort_values(by=["董事会日期"], ignore_index=True, inplace=True)
    return temp_df


if __name__ == "__main__":
    stock_fhps_detail_ths_df = stock_fhps_detail_ths(symbol="200596")
    print(stock_fhps_detail_ths_df)
