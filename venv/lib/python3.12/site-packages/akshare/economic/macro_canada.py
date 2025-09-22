#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/11/27 20:30
Desc: 东方财富-经济数据-加拿大
https://data.eastmoney.com/cjsj/foreign_5_0.html
"""

import pandas as pd
import requests


# 新屋开工
def macro_canada_new_house_rate() -> pd.DataFrame:
    """
    东方财富-经济数据-加拿大-新屋开工
    https://data.eastmoney.com/cjsj/foreign_7_0.html
    :return: 新屋开工
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_CA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00342247")',
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
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"]).dt.date
    return temp_df


# 失业率
def macro_canada_unemployment_rate() -> pd.DataFrame:
    """
    东方财富-经济数据-加拿大-失业率
    https://data.eastmoney.com/cjsj/foreign_7_1.html
    :return: 失业率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_CA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00157746")',
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
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"]).dt.date
    return temp_df


# 贸易帐
def macro_canada_trade() -> pd.DataFrame:
    """
    东方财富-经济数据-加拿大-贸易帐
    https://data.eastmoney.com/cjsj/foreign_7_2.html
    :return: 贸易帐
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_CA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00102022")',
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
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"]).dt.date
    return temp_df


# 零售销售月率
def macro_canada_retail_rate_monthly() -> pd.DataFrame:
    """
    东方财富-经济数据-加拿大-零售销售月率
    https://data.eastmoney.com/cjsj/foreign_7_3.html
    :return: 零售销售月率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_CA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG01337094")',
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
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"]).dt.date
    return temp_df


# 央行公布利率决议
def macro_canada_bank_rate() -> pd.DataFrame:
    """
    东方财富-经济数据-加拿大-央行公布利率决议
    https://data.eastmoney.com/cjsj/foreign_7_4.html
    :return: 央行公布利率决议
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_CA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00342248")',
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
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"]).dt.date
    return temp_df


# 核心消费者物价指数年率
def macro_canada_core_cpi_yearly() -> pd.DataFrame:
    """
    东方财富-经济数据-加拿大-核心消费者物价指数年率
    https://data.eastmoney.com/cjsj/foreign_7_5.html
    :return: 核心消费者物价指数年率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_CA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00102030")',
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
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"]).dt.date
    return temp_df


# 核心消费者物价指数月率
def macro_canada_core_cpi_monthly() -> pd.DataFrame:
    """
    东方财富-经济数据-加拿大-核心消费者物价指数月率
    https://data.eastmoney.com/cjsj/foreign_7_6.html
    :return: 核心消费者物价指数月率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_CA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00102044")',
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
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"]).dt.date
    return temp_df


# 消费者物价指数年率
def macro_canada_cpi_yearly() -> pd.DataFrame:
    """
    东方财富-经济数据-加拿大-消费者物价指数年率
    https://data.eastmoney.com/cjsj/foreign_7_7.html
    :return: 消费者物价指数年率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_CA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00102029")',
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
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"]).dt.date
    return temp_df


# 消费者物价指数月率
def macro_canada_cpi_monthly() -> pd.DataFrame:
    """
    东方财富-经济数据-加拿大-消费者物价指数月率
    https://data.eastmoney.com/cjsj/foreign_7_8.html
    :return: 消费者物价指数月率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_CA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00158719")',
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
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"]).dt.date
    return temp_df


# GDP 月率
def macro_canada_gdp_monthly() -> pd.DataFrame:
    """
    东方财富-经济数据-加拿大-GDP 月率
    https://data.eastmoney.com/cjsj/foreign_7_9.html
    :return: GDP 月率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_CA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00159259")',
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
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"]).dt.date
    return temp_df


if __name__ == "__main__":
    macro_canada_new_house_rate_df = macro_canada_new_house_rate()
    print(macro_canada_new_house_rate_df)

    macro_canada_unemployment_rate_df = macro_canada_unemployment_rate()
    print(macro_canada_unemployment_rate_df)

    macro_canada_trade_df = macro_canada_trade()
    print(macro_canada_trade_df)

    macro_canada_retail_rate_monthly_df = macro_canada_retail_rate_monthly()
    print(macro_canada_retail_rate_monthly_df)

    macro_canada_bank_rate_df = macro_canada_bank_rate()
    print(macro_canada_bank_rate_df)

    macro_canada_core_cpi_yearly_df = macro_canada_core_cpi_yearly()
    print(macro_canada_core_cpi_yearly_df)

    macro_canada_core_cpi_monthly_df = macro_canada_core_cpi_monthly()
    print(macro_canada_core_cpi_monthly_df)

    macro_canada_cpi_yearly_df = macro_canada_cpi_yearly()
    print(macro_canada_cpi_yearly_df)

    macro_canada_cpi_monthly_df = macro_canada_cpi_monthly()
    print(macro_canada_cpi_monthly_df)

    macro_canada_gdp_monthly_df = macro_canada_gdp_monthly()
    print(macro_canada_gdp_monthly_df)
