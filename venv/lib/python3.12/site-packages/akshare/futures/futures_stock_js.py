#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/24 18:10
Desc: 上海期货交易所指定交割仓库库存周报
https://datacenter.jin10.com/reportType/dc_shfe_weekly_stock
https://tsite.shfe.com.cn/statements/dataview.html?paramid=kx
"""

import pandas as pd
import requests


def futures_stock_shfe_js(date: str = "20240419") -> pd.DataFrame:
    """
    金十财经-上海期货交易所指定交割仓库库存周报
    https://datacenter.jin10.com/reportType/dc_shfe_weekly_stock
    :param date: 交易日; 库存周报只在每周的最后一个交易日公布数据
    :type date: str
    :return: 库存周报
    :rtype: pandas.Series
    """
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }
    url = "https://datacenter-api.jin10.com/reports/list"
    params = {
        "category": "stock",
        "date": "-".join([date[:4], date[4:6], date[6:]]),
        "attr_id": "1",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    columns_list = [item["name"] for item in data_json["data"]["keys"]]
    temp_df = pd.DataFrame(data_json["data"]["values"], columns=columns_list)
    for item in columns_list[1:]:
        temp_df[item] = pd.to_numeric(temp_df[item], errors="coerce")
    return temp_df


if __name__ == "__main__":
    futures_stock_shfe_js_df = futures_stock_shfe_js(date="20240419")
    print(futures_stock_shfe_js_df)
