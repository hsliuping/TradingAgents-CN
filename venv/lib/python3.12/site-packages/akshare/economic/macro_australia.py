#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/1/17 15:30
Desc: 东方财富-经济数据-澳大利亚
https://data.eastmoney.com/cjsj/foreign_5_0.html
"""

import pandas as pd
import requests


# 零售销售月率
def macro_australia_retail_rate_monthly() -> pd.DataFrame:
    """
    东方财富-经济数据-澳大利亚-零售销售月率
    https://data.eastmoney.com/cjsj/foreign_5_0.html
    :return: 零售销售月率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_AUSTRALIA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00152903")',
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "-",
        "-",
        "时间",
        "-",
        "发布日期",
        "现值",
        "前值",
    ]
    temp_df = temp_df[
        [
            "时间",
            "前值",
            "现值",
            "发布日期",
        ]
    ]
    temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
    temp_df["现值"] = pd.to_numeric(temp_df["现值"], errors="coerce")
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"], errors="coerce").dt.date
    temp_df.sort_values(by="发布日期", ignore_index=True, inplace=True)
    return temp_df


# 贸易帐
def macro_australia_trade() -> pd.DataFrame:
    """
    东方财富-经济数据-澳大利亚-贸易帐
    https://data.eastmoney.com/cjsj/foreign_5_1.html
    :return: 贸易帐
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_AUSTRALIA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00152793")',
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "-",
        "-",
        "时间",
        "-",
        "发布日期",
        "现值",
        "前值",
    ]
    temp_df = temp_df[
        [
            "时间",
            "前值",
            "现值",
            "发布日期",
        ]
    ]
    temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
    temp_df["现值"] = pd.to_numeric(temp_df["现值"], errors="coerce")
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"], errors="coerce").dt.date
    temp_df.sort_values(by="发布日期", ignore_index=True, inplace=True)
    return temp_df


# 失业率
def macro_australia_unemployment_rate() -> pd.DataFrame:
    """
    东方财富-经济数据-澳大利亚-失业率
    https://data.eastmoney.com/cjsj/foreign_5_2.html
    :return: 失业率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_AUSTRALIA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00101141")',
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "-",
        "-",
        "时间",
        "-",
        "发布日期",
        "现值",
        "前值",
    ]
    temp_df = temp_df[
        [
            "时间",
            "前值",
            "现值",
            "发布日期",
        ]
    ]
    temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
    temp_df["现值"] = pd.to_numeric(temp_df["现值"], errors="coerce")
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"], errors="coerce").dt.date
    temp_df.sort_values(by="发布日期", ignore_index=True, inplace=True)
    return temp_df


# 生产者物价指数季率
def macro_australia_ppi_quarterly() -> pd.DataFrame:
    """
    东方财富-经济数据-澳大利亚-生产者物价指数季率
    https://data.eastmoney.com/cjsj/foreign_5_3.html
    :return: 生产者物价指数季率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_AUSTRALIA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00152722")',
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "-",
        "-",
        "时间",
        "-",
        "发布日期",
        "现值",
        "前值",
    ]
    temp_df = temp_df[
        [
            "时间",
            "前值",
            "现值",
            "发布日期",
        ]
    ]
    temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
    temp_df["现值"] = pd.to_numeric(temp_df["现值"], errors="coerce")
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"], errors="coerce").dt.date
    temp_df.sort_values(by="发布日期", ignore_index=True, inplace=True)
    return temp_df


# 消费者物价指数季率
def macro_australia_cpi_quarterly() -> pd.DataFrame:
    """
    东方财富-经济数据-澳大利亚-消费者物价指数季率
    https://data.eastmoney.com/cjsj/foreign_5_4.html
    :return: 消费者物价指数季率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_AUSTRALIA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00101104")',
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "-",
        "-",
        "时间",
        "-",
        "发布日期",
        "现值",
        "前值",
    ]
    temp_df = temp_df[
        [
            "时间",
            "前值",
            "现值",
            "发布日期",
        ]
    ]
    temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
    temp_df["现值"] = pd.to_numeric(temp_df["现值"], errors="coerce")
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"], errors="coerce").dt.date
    temp_df.sort_values(by="发布日期", ignore_index=True, inplace=True)
    return temp_df


# 消费者物价指数年率
def macro_australia_cpi_yearly() -> pd.DataFrame:
    """
    东方财富-经济数据-澳大利亚-消费者物价指数年率
    https://data.eastmoney.com/cjsj/foreign_5_5.html
    :return: 消费者物价指数年率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_AUSTRALIA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00101093")',
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "-",
        "-",
        "时间",
        "-",
        "发布日期",
        "现值",
        "前值",
    ]
    temp_df = temp_df[
        [
            "时间",
            "前值",
            "现值",
            "发布日期",
        ]
    ]
    temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
    temp_df["现值"] = pd.to_numeric(temp_df["现值"], errors="coerce")
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"], errors="coerce").dt.date
    temp_df.sort_values(by="发布日期", ignore_index=True, inplace=True)
    return temp_df


# 央行公布利率决议
def macro_australia_bank_rate() -> pd.DataFrame:
    """
    东方财富-经济数据-澳大利亚-央行公布利率决议
    https://data.eastmoney.com/cjsj/foreign_5_6.html
    :return: 央行公布利率决议
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_AUSTRALIA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00342255")',
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "-",
        "-",
        "时间",
        "-",
        "发布日期",
        "现值",
        "前值",
    ]
    temp_df = temp_df[
        [
            "时间",
            "前值",
            "现值",
            "发布日期",
        ]
    ]
    temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
    temp_df["现值"] = pd.to_numeric(temp_df["现值"], errors="coerce")
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"], errors="coerce").dt.date
    temp_df.sort_values(by="发布日期", ignore_index=True, inplace=True)
    return temp_df


if __name__ == "__main__":
    macro_australia_retail_rate_monthly_df = macro_australia_retail_rate_monthly()
    print(macro_australia_retail_rate_monthly_df)

    macro_australia_trade_df = macro_australia_trade()
    print(macro_australia_trade_df)

    macro_australia_unemployment_rate_df = macro_australia_unemployment_rate()
    print(macro_australia_unemployment_rate_df)

    macro_australia_ppi_quarterly_df = macro_australia_ppi_quarterly()
    print(macro_australia_ppi_quarterly_df)

    macro_australia_cpi_quarterly_df = macro_australia_cpi_quarterly()
    print(macro_australia_cpi_quarterly_df)

    macro_australia_cpi_yearly_df = macro_australia_cpi_yearly()
    print(macro_australia_cpi_yearly_df)

    macro_australia_bank_rate_df = macro_australia_bank_rate()
    print(macro_australia_bank_rate_df)
