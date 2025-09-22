#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/1/20 23:00
Desc: 东方财富-数据中心-中国油价
https://data.eastmoney.com/cjsj/oil_default.html
"""

import pandas as pd
import requests


def energy_oil_hist() -> pd.DataFrame:
    """
    汽柴油历史调价信息
    https://data.eastmoney.com/cjsj/oil_default.html
    :return: 汽柴油历史调价信息
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPTA_WEB_YJ_BD",
        "columns": "ALL",
        "sortColumns": "dim_date",
        "sortTypes": "-1",
        "token": "894050c76af8597a853f5b408b759f5d",
        "pageNumber": "1",
        "pageSize": "1000",
        "source": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = ["调整日期", "汽油价格", "柴油价格", "汽油涨跌", "柴油涨跌"]
    temp_df["调整日期"] = pd.to_datetime(temp_df["调整日期"], errors="coerce").dt.date
    temp_df["汽油价格"] = pd.to_numeric(temp_df["汽油价格"], errors="coerce")
    temp_df["柴油价格"] = pd.to_numeric(temp_df["柴油价格"], errors="coerce")
    temp_df["汽油涨跌"] = pd.to_numeric(temp_df["汽油涨跌"], errors="coerce")
    temp_df["柴油涨跌"] = pd.to_numeric(temp_df["柴油涨跌"], errors="coerce")
    temp_df.sort_values(by=["调整日期"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


def energy_oil_detail(date: str = "20220517") -> pd.DataFrame:
    """
    全国各地区的汽油和柴油油价
    https://data.eastmoney.com/cjsj/oil_default.html
    :param date: 可以调用 ak.energy_oil_hist() 得到可以获取油价的调整时间
    :type date: str
    :return: oil price at specific date
    :rtype: pandas.DataFrame
    """
    date = "-".join([date[:4], date[4:6], date[6:]])
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPTA_WEB_YJ_JH",
        "columns": "ALL",
        "filter": f"(dim_date='{date}')",
        "sortColumns": "cityname",
        "sortTypes": "1",
        "token": "894050c76af8597a853f5b408b759f5d",
        "pageNumber": "1",
        "pageSize": "1000",
        "source": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"]).iloc[:, 1:]
    temp_df.columns = [
        "日期",
        "地区",
        "V_0",
        "V_92",
        "V_95",
        "V_89",
        "ZDE_0",
        "ZDE_92",
        "ZDE_95",
        "ZDE_89",
        "QE_0",
        "QE_92",
        "QE_95",
        "QE_89",
        "首字母",
    ]
    del temp_df["首字母"]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["V_0"] = pd.to_numeric(temp_df["V_0"], errors="coerce")
    temp_df["V_92"] = pd.to_numeric(temp_df["V_92"], errors="coerce")
    temp_df["V_95"] = pd.to_numeric(temp_df["V_95"], errors="coerce")
    temp_df["V_89"] = pd.to_numeric(temp_df["V_89"], errors="coerce")
    temp_df["ZDE_0"] = pd.to_numeric(temp_df["ZDE_0"], errors="coerce")
    temp_df["ZDE_92"] = pd.to_numeric(temp_df["ZDE_92"], errors="coerce")
    temp_df["ZDE_95"] = pd.to_numeric(temp_df["ZDE_95"], errors="coerce")
    temp_df["ZDE_89"] = pd.to_numeric(temp_df["ZDE_89"], errors="coerce")
    temp_df["QE_0"] = pd.to_numeric(temp_df["QE_0"], errors="coerce")
    temp_df["QE_92"] = pd.to_numeric(temp_df["QE_92"], errors="coerce")
    temp_df["QE_95"] = pd.to_numeric(temp_df["QE_95"], errors="coerce")
    temp_df["QE_89"] = pd.to_numeric(temp_df["QE_89"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    energy_oil_hist_df = energy_oil_hist()
    print(energy_oil_hist_df)

    energy_oil_detail_df = energy_oil_detail(date="20240118")
    print(energy_oil_detail_df)
