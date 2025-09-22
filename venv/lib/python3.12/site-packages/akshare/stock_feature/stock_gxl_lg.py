#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/4/10 16:05
Desc: 乐咕乐股-股息率-A 股股息率
https://legulegu.com/stockdata/guxilv
"""

import pandas as pd
import requests

from akshare.stock_feature.stock_a_indicator import get_token_lg, get_cookie_csrf


def stock_a_gxl_lg(symbol: str = "上证A股") -> pd.DataFrame:
    """
    乐咕乐股-股息率-A 股股息率
    https://legulegu.com/stockdata/guxilv
    :param symbol: choice of {"上证A股", "深证A股", "创业板", "科创板"}
    :type symbol: str
    :return: A 股股息率
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "上证A股": "shangzheng",
        "深证A股": "shenzheng",
        "创业板": "chuangyeban",
        "科创板": "kechuangban",
    }
    url = "https://legulegu.com/api/stockdata/guxilv"
    token = get_token_lg()
    params = {"token": token}
    r = requests.get(
        url,
        params=params,
        **get_cookie_csrf(url="https://legulegu.com/stockdata/guxilv"),
    )
    data_json = r.json()
    temp_df = pd.DataFrame(data_json[symbol_map[symbol]])
    temp_df["date"] = (
        pd.to_datetime(temp_df["date"], unit="ms") + pd.Timedelta(hours=8)
    ).dt.date
    temp_df.rename(columns={"addDvTtm": "股息率", "date": "日期"}, inplace=True)
    temp_df = temp_df[
        [
            "日期",
            "股息率",
        ]
    ]
    temp_df["股息率"] = pd.to_numeric(temp_df["股息率"], errors="coerce")
    return temp_df


def stock_hk_gxl_lg() -> pd.DataFrame:
    """
    乐咕乐股-股息率-恒生指数股息率
    https://legulegu.com/stockdata/market/hk/dv/hsi
    :return: 恒生指数股息率
    :rtype: pandas.DataFrame
    """
    url = "https://legulegu.com/api/stockdata/hs"
    token = get_token_lg()
    params = {"token": token, "indexCode": "HSI"}
    r = requests.get(
        url,
        params=params,
        **get_cookie_csrf(url="https://legulegu.com/stockdata/market/hk/dv/hsi"),
    )
    data_json = r.json()
    temp_df = pd.DataFrame(data_json)
    temp_df["date"] = (
        pd.to_datetime(temp_df["date"], unit="ms") + pd.Timedelta(hours=8)
    ).dt.date
    temp_df.rename(columns={"addDvRatio": "股息率", "date": "日期"}, inplace=True)
    temp_df = temp_df[
        [
            "日期",
            "股息率",
        ]
    ]
    temp_df["股息率"] = pd.to_numeric(temp_df["股息率"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_a_gxl_lg_df = stock_a_gxl_lg(symbol="上证A股")
    print(stock_a_gxl_lg_df)

    stock_hk_gxl_lg_df = stock_hk_gxl_lg()
    print(stock_hk_gxl_lg_df)
