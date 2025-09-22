#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/11/26 18:00
Desc: 东方财富网-数据中心-估值分析-每日互动-每日互动-估值分析
https://data.eastmoney.com/gzfx/detail/300766.html
"""

import pandas as pd

from akshare.request import make_request_with_retry_json


def stock_value_em(symbol: str = "300766") -> pd.DataFrame:
    """
    东方财富网-数据中心-估值分析-每日互动-每日互动-估值分析
    https://data.eastmoney.com/gzfx/detail/300766.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 估值分析
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_VALUEANALYSIS_DET",
        "columns": "ALL",
        "quoteColumns": "",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(SECURITY_CODE="{symbol}")',
    }
    data_json = make_request_with_retry_json(url, params=params)
    temp_json = data_json["result"]["data"]
    temp_df = pd.DataFrame(temp_json)
    temp_df.rename(
        columns={
            "TRADE_DATE": "数据日期",
            "CLOSE_PRICE": "当日收盘价",
            "CHANGE_RATE": "当日涨跌幅",
            "TOTAL_MARKET_CAP": "总市值",
            "NOTLIMITED_MARKETCAP_A": "流通市值",
            "TOTAL_SHARES": "总股本",
            "FREE_SHARES_A": "流通股本",
            "PE_TTM": "PE(TTM)",
            "PE_LAR": "PE(静)",
            "PB_MRQ": "市净率",
            "PEG_CAR": "PEG值",
            "PCF_OCF_TTM": "市现率",
            "PS_TTM": "市销率",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "数据日期",
            "当日收盘价",
            "当日涨跌幅",
            "总市值",
            "流通市值",
            "总股本",
            "流通股本",
            "PE(TTM)",
            "PE(静)",
            "市净率",
            "PEG值",
            "市现率",
            "市销率",
        ]
    ]
    temp_df["数据日期"] = pd.to_datetime(temp_df["数据日期"], errors="coerce").dt.date
    for item in temp_df.columns[1:]:
        temp_df[item] = pd.to_numeric(temp_df[item], errors="coerce")
    temp_df.sort_values(by="数据日期", ignore_index=True, inplace=True)
    return temp_df


if __name__ == "__main__":
    stock_value_em_df = stock_value_em(symbol="300766")
    print(stock_value_em_df)
