#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/29 23:00
Desc: 百度股市通-A股-财务报表-估值数据
https://gushitong.baidu.com/stock/ab-002044
"""

import pandas as pd
import requests


def stock_zh_valuation_baidu(
    symbol: str = "002044", indicator: str = "总市值", period: str = "近一年"
) -> pd.DataFrame:
    """
    百度股市通-A股-财务报表-估值数据
    https://gushitong.baidu.com/stock/ab-002044
    :param symbol: 股票代码
    :type symbol: str
    :param indicator: choice of {"总市值", "市盈率(TTM)", "市盈率(静)", "市净率", "市现率"}
    :type indicator: str
    :param period: choice of {"近一年", "近三年", "近五年", "近十年", "全部"}
    :type period: str
    :return: 估值数据
    :rtype: pandas.DataFrame
    """
    url = "https://gushitong.baidu.com/opendata"
    params = {
        "openapi": "1",
        "dspName": "iphone",
        "tn": "tangram",
        "client": "app",
        "query": indicator,
        "code": symbol,
        "word": "",
        "resource_id": "51171",
        "market": "ab",
        "tag": indicator,
        "chart_select": period,
        "industry_select": "",
        "skip_industry": "1",
        "finClientType": "pc",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(
        data_json["Result"][0]["DisplayData"]["resultData"]["tplData"]["result"][
            "chartInfo"
        ][0]["body"]
    )
    temp_df.columns = ["date", "value"]
    temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_zh_valuation_baidu_df = stock_zh_valuation_baidu(
        symbol="002044", indicator="总市值", period="近一年"
    )
    print(stock_zh_valuation_baidu_df)
