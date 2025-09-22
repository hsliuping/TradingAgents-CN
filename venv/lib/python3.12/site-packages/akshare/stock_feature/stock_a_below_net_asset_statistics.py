#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/30 10:30
Desc: 破净股统计历史走势
https://www.legulegu.com/stockdata/below-net-asset-statistics
"""

import pandas as pd
import requests

from akshare.utils.cons import headers


def stock_a_below_net_asset_statistics(symbol: str = "全部A股") -> pd.DataFrame:
    """
    破净股统计历史走势
    https://www.legulegu.com/stockdata/below-net-asset-statistics
    :param symbol: choice of {"全部A股", "沪深300", "上证50", "中证500"}
    :type symbol: str
    :return: 破净股统计历史走势
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "全部A股": "1",
        "沪深300": "000300.XSHG",
        "上证50": "000016.SH",
        "中证500": "000905.SH",
    }
    url = "https://legulegu.com/stockdata/below-net-asset-statistics-data"
    params = {
        "marketId": symbol_map[symbol],
        "token": "325843825a2745a2a8f9b9e3355cb864",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json)
    temp_df["date"] = pd.to_datetime(temp_df["date"], unit="ms").dt.date
    del temp_df["marketId"]
    big_df = temp_df.iloc[:, :3]
    big_df.columns = ["below_net_asset", "total_company", "date"]
    big_df["below_net_asset_ratio"] = round(
        big_df["below_net_asset"] / big_df["total_company"], 4
    )
    big_df = big_df[
        ["date", "below_net_asset", "total_company", "below_net_asset_ratio"]
    ]
    big_df["date"] = pd.to_datetime(big_df["date"], errors="coerce").dt.date
    big_df["below_net_asset"] = pd.to_numeric(
        big_df["below_net_asset"], errors="coerce"
    )
    big_df["total_company"] = pd.to_numeric(big_df["total_company"], errors="coerce")
    big_df["below_net_asset_ratio"] = pd.to_numeric(
        big_df["below_net_asset_ratio"], errors="coerce"
    )
    big_df.sort_values(["date"], inplace=True, ignore_index=True)
    return big_df


if __name__ == "__main__":
    stock_a_below_net_asset_statistics_df = stock_a_below_net_asset_statistics(
        symbol="全部A股"
    )
    print(stock_a_below_net_asset_statistics_df)

    stock_a_below_net_asset_statistics_df = stock_a_below_net_asset_statistics(
        symbol="沪深300"
    )
    print(stock_a_below_net_asset_statistics_df)

    stock_a_below_net_asset_statistics_df = stock_a_below_net_asset_statistics(
        symbol="上证50"
    )
    print(stock_a_below_net_asset_statistics_df)

    stock_a_below_net_asset_statistics_df = stock_a_below_net_asset_statistics(
        symbol="中证500"
    )
    print(stock_a_below_net_asset_statistics_df)
