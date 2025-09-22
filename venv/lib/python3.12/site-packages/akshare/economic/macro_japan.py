#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/3 16:00
Desc: 东方财富-经济数据-日本
https://data.eastmoney.com/cjsj/foreign_3_0.html
"""

import pandas as pd
import requests


def macro_japan_core(symbol: str = "EMG00341602") -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-宏观经济-日本-核心代码
    https://data.eastmoney.com/cjsj/foreign_1_0.html
    :param symbol: 代码
    :type symbol: str
    :return: 指定 symbol 的数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_JPAN",
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
    temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
    temp_df["现值"] = pd.to_numeric(temp_df["现值"], errors="coerce")
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"], errors="coerce").dt.date
    temp_df.sort_values(["发布日期"], inplace=True, ignore_index=True)
    return temp_df


# 央行公布利率决议
def macro_japan_bank_rate() -> pd.DataFrame:
    """
    东方财富-经济数据-日本-央行公布利率决议
    https://data.eastmoney.com/cjsj/foreign_3_0.html
    :return: 央行公布利率决议
    :rtype: pandas.DataFrame
    """
    temp_df = macro_japan_core(symbol="EMG00342252")
    return temp_df


# 全国消费者物价指数年率
def macro_japan_cpi_yearly() -> pd.DataFrame:
    """
    东方财富-经济数据-日本-全国消费者物价指数年率
    https://data.eastmoney.com/cjsj/foreign_3_1.html
    :return: 全国消费者物价指数年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_japan_core(symbol="EMG00005004")
    return temp_df


# 全国核心消费者物价指数年率
def macro_japan_core_cpi_yearly() -> pd.DataFrame:
    """
    东方财富-经济数据-日本-全国核心消费者物价指数年率
    https://data.eastmoney.com/cjsj/foreign_2_2.html
    :return: 全国核心消费者物价指数年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_japan_core(symbol="EMG00158099")
    return temp_df


# 失业率
def macro_japan_unemployment_rate() -> pd.DataFrame:
    """
    东方财富-经济数据-日本-失业率
    https://data.eastmoney.com/cjsj/foreign_2_3.html
    :return: 失业率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_japan_core(symbol="EMG00005047")
    return temp_df


# 领先指标终值
def macro_japan_head_indicator() -> pd.DataFrame:
    """
    东方财富-经济数据-日本-领先指标终值
    https://data.eastmoney.com/cjsj/foreign_3_4.html
    :return: 领先指标终值
    :rtype: pandas.DataFrame
    """
    temp_df = macro_japan_core(symbol="EMG00005117")
    return temp_df


if __name__ == "__main__":
    macro_japan_bank_rate_df = macro_japan_bank_rate()
    print(macro_japan_bank_rate_df)

    macro_japan_cpi_yearly_df = macro_japan_cpi_yearly()
    print(macro_japan_cpi_yearly_df)

    macro_japan_core_cpi_yearly_df = macro_japan_core_cpi_yearly()
    print(macro_japan_core_cpi_yearly_df)

    macro_japan_unemployment_rate_df = macro_japan_unemployment_rate()
    print(macro_japan_unemployment_rate_df)

    macro_japan_head_indicator_df = macro_japan_head_indicator()
    print(macro_japan_head_indicator_df)
