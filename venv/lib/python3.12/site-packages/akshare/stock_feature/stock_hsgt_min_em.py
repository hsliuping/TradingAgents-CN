# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/2/5 18:00
Desc: 东方财富网-数据中心-沪深港通-市场概括
https://data.eastmoney.com/hsgt/hsgtDetail/scgk.html
"""

import pandas as pd
import requests


def stock_hsgt_fund_min_em(symbol: str = "北向资金") -> pd.DataFrame:
    """
    东方财富-数据中心-沪深港通-市场概括-分时数据
    https://data.eastmoney.com/hsgt/hsgtDetail/scgk.html
    :param symbol: 北向资金; choice of {"北向资金", "南向资金"}
    :type symbol: str
    :return: 沪深港通持股-分时数据
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/kamtbs.rtmin/get"
    params = {
        "fields1": "f1,f2,f3,f4",
        "fields2": "f51,f54,f52,f58,f53,f62,f56,f57,f60,f61",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "_": "1707125786160",
    }
    r = requests.get(url, params=params)
    data_json = r.json()

    if symbol == "南向资金":
        n2s_str_list = data_json["data"]["n2s"]
        temp_df = pd.DataFrame([item.split(",") for item in n2s_str_list])
        temp_df["date"] = data_json["data"]["n2sDate"]
        temp_df = temp_df.iloc[:, [0, 1, 3, 5, -1]]
        temp_df.columns = ["时间", "港股通(沪)", "港股通(深)", "南向资金", "日期"]
        temp_df = temp_df[["日期", "时间", "港股通(沪)", "港股通(深)", "南向资金"]]
        temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
        temp_df["港股通(沪)"] = pd.to_numeric(temp_df["港股通(沪)"], errors="coerce")
        temp_df["港股通(深)"] = pd.to_numeric(temp_df["港股通(深)"], errors="coerce")
        temp_df["南向资金"] = pd.to_numeric(temp_df["南向资金"], errors="coerce")
        return temp_df
    else:
        s2n_str_list = data_json["data"]["s2n"]
        temp_df = pd.DataFrame([item.split(",") for item in s2n_str_list])
        temp_df["date"] = data_json["data"]["s2nDate"]
        temp_df = temp_df.iloc[:, [0, 1, 3, 5, -1]]
        temp_df.columns = ["时间", "沪股通", "深股通", "北向资金", "日期"]
        temp_df = temp_df[["日期", "时间", "沪股通", "深股通", "北向资金"]]
        temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
        temp_df["沪股通"] = pd.to_numeric(temp_df["沪股通"], errors="coerce")
        temp_df["深股通"] = pd.to_numeric(temp_df["深股通"], errors="coerce")
        temp_df["北向资金"] = pd.to_numeric(temp_df["北向资金"], errors="coerce")
        return temp_df


if __name__ == "__main__":
    stock_hsgt_fund_min_em_df = stock_hsgt_fund_min_em(symbol="北向资金")
    print(stock_hsgt_fund_min_em_df)

    stock_hsgt_fund_min_em_df = stock_hsgt_fund_min_em(symbol="南向资金")
    print(stock_hsgt_fund_min_em_df)
