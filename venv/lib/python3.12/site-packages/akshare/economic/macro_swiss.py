#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/11/8 10:00
Desc: 东方财富-经济数据-瑞士
http://data.eastmoney.com/cjsj/foreign_2_0.html
"""

import pandas as pd
import requests


def macro_swiss_core(symbol: str = "EMG00341602") -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-宏观经济-瑞士-核心代码
    https://data.eastmoney.com/cjsj/foreign_1_0.html
    :param symbol: 代码
    :type symbol: str
    :return: 指定 symbol 的数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_CH",
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


# SVME采购经理人指数
def macro_swiss_svme():
    """
    东方财富-经济数据-瑞士-SVME采购经理人指数
    http://data.eastmoney.com/cjsj/foreign_2_0.html
    :return: SVME采购经理人指数
    :rtype: pandas.DataFrame
    """
    temp_df = macro_swiss_core(symbol="EMG00341602")
    return temp_df


# 贸易帐
def macro_swiss_trade():
    """
    东方财富-经济数据-瑞士-贸易帐
    http://data.eastmoney.com/cjsj/foreign_2_1.html
    :return: 贸易帐
    :rtype: pandas.DataFrame
    """
    temp_df = macro_swiss_core(symbol="EMG00341603")
    return temp_df


# 消费者物价指数年率
def macro_swiss_cpi_yearly():
    """
    东方财富-经济数据-瑞士-消费者物价指数年率
    http://data.eastmoney.com/cjsj/foreign_2_2.html
    :return: 消费者物价指数年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_swiss_core(symbol="EMG00341604")
    return temp_df


# GDP季率
def macro_swiss_gdp_quarterly():
    """
    东方财富-经济数据-瑞士-GDP季率
    http://data.eastmoney.com/cjsj/foreign_2_3.html
    :return: GDP季率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_swiss_core(symbol="EMG00341600")
    return temp_df


# GDP年率
def macro_swiss_gbd_yearly():
    """
    东方财富-经济数据-瑞士-GDP 年率
    http://data.eastmoney.com/cjsj/foreign_2_4.html
    :return: GDP年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_swiss_core(symbol="EMG00341601")
    return temp_df


# 央行公布利率决议
def macro_swiss_gbd_bank_rate():
    """
    东方财富-经济数据-瑞士-央行公布利率决议
    http://data.eastmoney.com/cjsj/foreign_2_5.html
    :return: 央行公布利率决议
    :rtype: pandas.DataFrame
    """
    temp_df = macro_swiss_core(symbol="EMG00341606")
    return temp_df


if __name__ == "__main__":
    macro_swiss_svme_df = macro_swiss_svme()
    print(macro_swiss_svme_df)

    macro_swiss_trade_df = macro_swiss_trade()
    print(macro_swiss_trade_df)

    macro_swiss_cpi_yearly_df = macro_swiss_cpi_yearly()
    print(macro_swiss_cpi_yearly_df)

    macro_swiss_gdp_quarterly_df = macro_swiss_gdp_quarterly()
    print(macro_swiss_gdp_quarterly_df)

    macro_swiss_gbd_yearly_df = macro_swiss_gbd_yearly()
    print(macro_swiss_gbd_yearly_df)

    macro_swiss_gbd_bank_rate_df = macro_swiss_gbd_bank_rate()
    print(macro_swiss_gbd_bank_rate_df)
