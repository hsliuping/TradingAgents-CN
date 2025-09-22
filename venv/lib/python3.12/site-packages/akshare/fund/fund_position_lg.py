#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/4/5 22:05
Desc: 乐咕乐股-基金仓位
https://legulegu.com/stockdata/fund-position/pos-stock
"""

import pandas as pd
import requests

from akshare.stock_feature.stock_a_indicator import get_token_lg, get_cookie_csrf


def fund_stock_position_lg() -> pd.DataFrame:
    """
    乐咕乐股-基金仓位-股票型基金仓位
    https://legulegu.com/stockdata/fund-position/pos-stock
    :return: 股票型基金仓位
    :rtype: pandas.DataFrame
    """
    url = "https://legulegu.com/api/stockdata/fund-position"
    token = get_token_lg()
    params = {
        "token": token,
        "type": "pos_stock",
        "category": "总仓位",
        "marketId": "5",
    }
    r = requests.get(
        url,
        params=params,
        **get_cookie_csrf(url="https://legulegu.com/stockdata/fund-position/pos-stock"),
    )
    data_json = r.json()
    temp_df = pd.DataFrame(data_json)
    temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
    temp_df = temp_df[
        [
            "date",
            "close",
            "position",
        ]
    ]
    temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
    temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    temp_df["position"] = pd.to_numeric(temp_df["position"], errors="coerce")
    return temp_df


def fund_balance_position_lg() -> pd.DataFrame:
    """
    乐咕乐股-基金仓位-平衡混合型基金仓位
    https://legulegu.com/stockdata/fund-position/pos-pingheng
    :return: 平衡混合型基金仓位
    :rtype: pandas.DataFrame
    """
    url = "https://legulegu.com/api/stockdata/fund-position"
    token = get_token_lg()
    params = {
        "token": token,
        "type": "pos_pingheng",
        "category": "总仓位",
        "marketId": "5",
    }
    r = requests.get(
        url,
        params=params,
        **get_cookie_csrf(
            url="https://legulegu.com/stockdata/fund-position/pos-pingheng"
        ),
    )
    data_json = r.json()
    temp_df = pd.DataFrame(data_json)
    temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
    temp_df = temp_df[
        [
            "date",
            "close",
            "position",
        ]
    ]
    temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
    temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    temp_df["position"] = pd.to_numeric(temp_df["position"], errors="coerce")
    return temp_df


def fund_linghuo_position_lg() -> pd.DataFrame:
    """
    乐咕乐股-基金仓位-灵活配置型基金仓位
    https://legulegu.com/stockdata/fund-position/pos-linghuo
    :return: 灵活配置型基金仓位
    :rtype: pandas.DataFrame
    """
    url = "https://legulegu.com/api/stockdata/fund-position"
    token = get_token_lg()
    params = {
        "token": token,
        "type": "pos_linghuo",
        "category": "总仓位",
        "marketId": "5",
    }
    r = requests.get(
        url,
        params=params,
        **get_cookie_csrf(
            url="https://legulegu.com/stockdata/fund-position/pos-linghuo"
        ),
    )
    data_json = r.json()
    temp_df = pd.DataFrame(data_json)
    temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
    temp_df = temp_df[
        [
            "date",
            "close",
            "position",
        ]
    ]
    temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
    temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    temp_df["position"] = pd.to_numeric(temp_df["position"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    fund_stock_position_lg_df = fund_stock_position_lg()
    print(fund_stock_position_lg_df)

    fund_balance_position_lg_df = fund_balance_position_lg()
    print(fund_balance_position_lg_df)

    fund_linghuo_position_lg_df = fund_linghuo_position_lg()
    print(fund_linghuo_position_lg_df)
