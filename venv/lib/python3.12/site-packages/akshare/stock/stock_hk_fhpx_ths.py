#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/1/16 15:30
Desc: 同花顺-港股-分红派息
https://stockpage.10jqka.com.cn/HK0700/bonus/
"""

from io import StringIO

import pandas as pd
import requests


def stock_hk_fhpx_detail_ths(symbol: str = "0700") -> pd.DataFrame:
    """
    同花顺-港股-分红派息
    https://stockpage.10jqka.com.cn/HK0700/bonus/
    :param symbol: 港股代码
    :type symbol: str
    :return: 分红派息
    :rtype: pandas.DataFrame
    """
    url = f"https://basic.10jqka.com.cn/176/HK{symbol}/bonus.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/89.0.4389.90 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    r.encoding = "utf-8"
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df.columns = [
        "公告日期",
        "方案",
        "除净日",
        "派息日",
        "过户日期起止日-起始",
        "过户日期起止日-截止",
        "类型",
        "进度",
        "以股代息",
    ]
    # 剔除异常格式，由以股代息产生的异常
    temp_df.dropna(subset=["派息日", "除净日"], inplace=True, ignore_index=True)
    temp_df["公告日期"] = pd.to_datetime(
        temp_df["公告日期"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df["除净日"] = pd.to_datetime(
        temp_df["除净日"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df["派息日"] = pd.to_datetime(
        temp_df["派息日"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df["过户日期起止日-起始"] = pd.to_datetime(
        temp_df["过户日期起止日-起始"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df["过户日期起止日-截止"] = pd.to_datetime(
        temp_df["过户日期起止日-截止"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df.sort_values(["公告日期"], inplace=True, ignore_index=True)
    return temp_df


if __name__ == "__main__":
    stock_hk_fhpx_detail_ths_df = stock_hk_fhpx_detail_ths(symbol="0700")
    print(stock_hk_fhpx_detail_ths_df)
