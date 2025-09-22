#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/11/12 17:14
Desc: 东方财富-经济数据-英国
https://data.eastmoney.com/cjsj/foreign_4_0.html
"""

import pandas as pd
import requests


def macro_uk_core(symbol: str = "EMG00010348") -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-宏观经济-英国-核心代码
    https://data.eastmoney.com/cjsj/foreign_4_0.html
    :param symbol: 代码
    :type symbol: str
    :return: 指定 symbol 的数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_BRITAIN",
        "columns": "ALL",
        "filter": f'(INDICATOR_ID="{symbol}")',
        "pageNumber": "1",
        "pageSize": "5000",
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
    temp_df.rename(
        columns={
            "COUNTRY": "-",
            "INDICATOR_ID": "-",
            "INDICATOR_NAME": "-",
            "REPORT_DATE_CH": "时间",
            "REPORT_DATE": "-",
            "PUBLISH_DATE": "发布日期",
            "VALUE": "现值",
            "PRE_VALUE": "前值",
            "INDICATOR_IDOLD": "-",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "时间",
            "前值",
            "现值",
            "发布日期",
        ]
    ]
    temp_df["前值"] = pd.to_numeric(temp_df["前值"])
    temp_df["现值"] = pd.to_numeric(temp_df["现值"])
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"]).dt.date
    temp_df.sort_values(["发布日期"], inplace=True, ignore_index=True)
    return temp_df


# Halifax房价指数月率
def macro_uk_halifax_monthly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-Halifax 房价指数月率
    https://data.eastmoney.com/cjsj/foreign_4_0.html
    :return: Halifax 房价指数月率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00342256")
    return temp_df


# Halifax 房价指数年率
def macro_uk_halifax_yearly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-Halifax 房价指数年率
    https://data.eastmoney.com/cjsj/foreign_4_1.html
    :return: Halifax房价指数年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00010370")
    return temp_df


# 贸易帐
def macro_uk_trade() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-贸易帐
    https://data.eastmoney.com/cjsj/foreign_4_2.html
    :return: 贸易帐
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00158309")
    return temp_df


# 央行公布利率决议
def macro_uk_bank_rate() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-央行公布利率决议
    https://data.eastmoney.com/cjsj/foreign_4_3.html
    :return: 央行公布利率决议
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00342253")
    return temp_df


# 核心消费者物价指数年率
def macro_uk_core_cpi_yearly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-核心消费者物价指数年率
    https://data.eastmoney.com/cjsj/foreign_4_4.html
    :return: 核心消费者物价指数年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00010279")
    return temp_df


# 核心消费者物价指数月率
def macro_uk_core_cpi_monthly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-核心消费者物价指数月率
    https://data.eastmoney.com/cjsj/foreign_4_5.html
    :return: 核心消费者物价指数月率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00010291")
    return temp_df


# 消费者物价指数年率
def macro_uk_cpi_yearly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-消费者物价指数年率
    https://data.eastmoney.com/cjsj/foreign_4_6.html
    :return: 消费者物价指数年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00010267")
    return temp_df


# 消费者物价指数月率
def macro_uk_cpi_monthly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-消费者物价指数月率
    https://data.eastmoney.com/cjsj/foreign_4_7.html
    :return: 消费者物价指数月率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00010291")
    return temp_df


# 零售销售月率
def macro_uk_retail_monthly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-零售销售月率
    https://data.eastmoney.com/cjsj/foreign_4_8.html
    :return: 零售销售月率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00158298")
    return temp_df


# 零售销售年率
def macro_uk_retail_yearly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-零售销售年率
    https://data.eastmoney.com/cjsj/foreign_4_9.html
    :return: 零售销售年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00158297")
    return temp_df


# Rightmove 房价指数年率
def macro_uk_rightmove_yearly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-Rightmove 房价指数年率
    https://data.eastmoney.com/cjsj/foreign_4_10.html
    :return: Rightmove 房价指数年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00341608")
    return temp_df


# Rightmove 房价指数月率
def macro_uk_rightmove_monthly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-Rightmove 房价指数月率
    https://data.eastmoney.com/cjsj/foreign_4_11.html
    :return: Rightmove 房价指数月率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00341607")
    return temp_df


# GDP 季率初值
def macro_uk_gdp_quarterly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-GDP 季率初值
    https://data.eastmoney.com/cjsj/foreign_4_12.html
    :return: GDP 季率初值
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00158277")
    return temp_df


# GDP 年率初值
def macro_uk_gdp_yearly() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-GDP 年率初值
    https://data.eastmoney.com/cjsj/foreign_4_13.html
    :return: GDP 年率初值
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00158276")
    return temp_df


# 失业率
def macro_uk_unemployment_rate() -> pd.DataFrame:
    """
    东方财富-经济数据-英国-失业率
    https://data.eastmoney.com/cjsj/foreign_4_14.html
    :return: 失业率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_uk_core(symbol="EMG00010348")
    return temp_df


if __name__ == "__main__":
    macro_uk_halifax_monthly_df = macro_uk_halifax_monthly()
    print(macro_uk_halifax_monthly_df)

    macro_uk_halifax_yearly_df = macro_uk_halifax_yearly()
    print(macro_uk_halifax_yearly_df)

    macro_uk_trade_df = macro_uk_trade()
    print(macro_uk_trade_df)

    macro_uk_bank_rate_df = macro_uk_bank_rate()
    print(macro_uk_bank_rate_df)

    macro_uk_core_cpi_yearly_df = macro_uk_core_cpi_yearly()
    print(macro_uk_core_cpi_yearly_df)

    macro_uk_core_cpi_monthly_df = macro_uk_core_cpi_monthly()
    print(macro_uk_core_cpi_monthly_df)

    macro_uk_cpi_yearly_df = macro_uk_cpi_yearly()
    print(macro_uk_cpi_yearly_df)

    macro_uk_cpi_monthly_df = macro_uk_cpi_monthly()
    print(macro_uk_cpi_monthly_df)

    macro_uk_retail_monthly_df = macro_uk_retail_monthly()
    print(macro_uk_retail_monthly_df)

    macro_uk_retail_yearly_df = macro_uk_retail_yearly()
    print(macro_uk_retail_yearly_df)

    macro_uk_rightmove_yearly_df = macro_uk_rightmove_yearly()
    print(macro_uk_rightmove_yearly_df)

    macro_uk_rightmove_monthly_df = macro_uk_rightmove_monthly()
    print(macro_uk_rightmove_monthly_df)

    macro_uk_gdp_quarterly_df = macro_uk_gdp_quarterly()
    print(macro_uk_gdp_quarterly_df)

    macro_uk_gdp_yearly_df = macro_uk_gdp_yearly()
    print(macro_uk_gdp_yearly_df)

    macro_uk_unemployment_rate_df = macro_uk_unemployment_rate()
    print(macro_uk_unemployment_rate_df)
