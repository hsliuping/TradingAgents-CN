#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/3/21 11:16
Desc: 行情宝
https://hqb.nxin.com/pigindex/index.shtml
"""

import pandas as pd
import requests


def index_hog_spot_price() -> pd.DataFrame:
    """
    行情宝-生猪市场价格指数
    https://hqb.nxin.com/pigindex/index.shtml
    :return: 生猪市场价格指数
    :rtype: pandas.DataFrame
    """
    url = "https://hqb.nxin.com/pigindex/getPigIndexChart.shtml"
    params = {"regionId": "0"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = [
        "日期",
        "指数",
        "4个月均线",
        "6个月均线",
        "12个月均线",
        "预售均价",
        "成交均价",
        "成交均重",
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms") + pd.Timedelta(hours=8)
    ).dt.date
    temp_df["指数"] = pd.to_numeric(temp_df["指数"], errors="coerce")
    temp_df["4个月均线"] = pd.to_numeric(temp_df["4个月均线"], errors="coerce")
    temp_df["6个月均线"] = pd.to_numeric(temp_df["6个月均线"], errors="coerce")
    temp_df["12个月均线"] = pd.to_numeric(temp_df["12个月均线"], errors="coerce")
    temp_df["预售均价"] = pd.to_numeric(temp_df["预售均价"], errors="coerce")
    temp_df["成交均价"] = pd.to_numeric(temp_df["成交均价"], errors="coerce")
    temp_df["成交均重"] = pd.to_numeric(temp_df["成交均重"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    index_hog_spot_price_df = index_hog_spot_price()
    print(index_hog_spot_price_df)
