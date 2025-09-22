#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/6/19 18:16
Desc: 浙江省排污权交易指数
https://zs.zjpwq.net/
"""

import pandas as pd
import requests


def index_eri(symbol: str = "月度") -> pd.DataFrame:
    """
    浙江省排污权交易指数
    https://zs.zjpwq.net
    :param symbol: choice of {"月度", "季度"}
    :type symbol: str
    :return: 浙江省排污权交易指数
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "月度": "MONTH",
        "季度": "QUARTER",
    }
    url = "https://zs.zjpwq.net/pwq-index-webapi/indexData"
    params = {
        "cycle": symbol_map[symbol],
        "regionId": "1",
        "structId": "1",
        "pageSize": "5000",
        "indexId": "1",
        "orderBy": "stage.publishTime",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    index_value = temp_df["indexValue"].tolist()
    index_time = [item["stage"]["publishTime"] for item in data_json["data"]]
    big_df = pd.DataFrame([index_time, index_value], index=["日期", "交易指数"]).T
    url = "https://zs.zjpwq.net/pwq-index-webapi/dataStatistics"
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    big_df["成交量"] = temp_df["totalQuantity"].tolist()
    big_df["成交额"] = temp_df["totalCost"].tolist()
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["交易指数"] = pd.to_numeric(big_df["交易指数"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["成交额"] = pd.to_numeric(big_df["成交额"], errors="coerce")
    return big_df


if __name__ == "__main__":
    index_eri_df = index_eri(symbol="月度")
    print(index_eri_df)

    index_eri_df = index_eri(symbol="季度")
    print(index_eri_df)
