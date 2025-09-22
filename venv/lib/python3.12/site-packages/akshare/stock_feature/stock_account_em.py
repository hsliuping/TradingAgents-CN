#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/21 17:00
Desc: 东方财富网-数据中心-特色数据-股票账户统计
东方财富网-数据中心-特色数据-股票账户统计: 股票账户统计详细数据
https://data.eastmoney.com/cjsj/gpkhsj.html
"""

import pandas as pd
import requests


def stock_account_statistics_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-股票账户统计
    https://data.eastmoney.com/cjsj/gpkhsj.html
    :return: 股票账户统计数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_STOCK_OPEN_DATA",
        "columns": "ALL",
        "pageSize": "500",
        "sortColumns": "STATISTICS_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
        "pageNumber": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "数据日期",
        "新增投资者-数量",
        "新增投资者-环比",
        "新增投资者-同比",
        "期末投资者-总量",
        "期末投资者-A股账户",
        "期末投资者-B股账户",
        "上证指数-收盘",
        "上证指数-涨跌幅",
        "沪深总市值",
        "沪深户均市值",
        "-",
    ]
    temp_df = temp_df[
        [
            "数据日期",
            "新增投资者-数量",
            "新增投资者-环比",
            "新增投资者-同比",
            "期末投资者-总量",
            "期末投资者-A股账户",
            "期末投资者-B股账户",
            "沪深总市值",
            "沪深户均市值",
            "上证指数-收盘",
            "上证指数-涨跌幅",
        ]
    ]
    temp_df["新增投资者-数量"] = pd.to_numeric(
        temp_df["新增投资者-数量"], errors="coerce"
    )
    temp_df["新增投资者-环比"] = pd.to_numeric(
        temp_df["新增投资者-环比"], errors="coerce"
    )
    temp_df["新增投资者-同比"] = pd.to_numeric(
        temp_df["新增投资者-同比"], errors="coerce"
    )
    temp_df["期末投资者-总量"] = pd.to_numeric(
        temp_df["期末投资者-总量"], errors="coerce"
    )
    temp_df["期末投资者-A股账户"] = pd.to_numeric(
        temp_df["期末投资者-A股账户"], errors="coerce"
    )
    temp_df["期末投资者-B股账户"] = pd.to_numeric(
        temp_df["期末投资者-B股账户"], errors="coerce"
    )
    temp_df["沪深总市值"] = pd.to_numeric(temp_df["沪深总市值"], errors="coerce")
    temp_df["沪深户均市值"] = pd.to_numeric(temp_df["沪深户均市值"], errors="coerce")
    temp_df["上证指数-收盘"] = pd.to_numeric(temp_df["上证指数-收盘"], errors="coerce")
    temp_df["上证指数-涨跌幅"] = pd.to_numeric(
        temp_df["上证指数-涨跌幅"], errors="coerce"
    )
    temp_df.sort_values(["数据日期"], ignore_index=True, inplace=True)
    return temp_df


if __name__ == "__main__":
    stock_account_statistics_em_df = stock_account_statistics_em()
    print(stock_account_statistics_em_df)
