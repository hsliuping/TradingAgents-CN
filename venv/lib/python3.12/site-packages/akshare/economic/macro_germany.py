#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/11/5 17:08
Desc: 东方财富-德国-经济数据
"""

import pandas as pd
import requests


def macro_germany_core(symbol: str = "EMG00179154") -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-宏观经济-德国-核心代码
    https://data.eastmoney.com/cjsj/foreign_1_0.html
    :param symbol: 代码
    :type symbol: str
    :return: 指定 symbol 的数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_GER",
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


# 东方财富-德国-经济数据-IFO商业景气指数
def macro_germany_ifo() -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-德国-IFO商业景气指数
    https://data.eastmoney.com/cjsj/foreign_1_0.html
    :return: IFO商业景气指数
    :rtype: pandas.DataFrame
    """
    temp_df = macro_germany_core(symbol="EMG00179154")
    return temp_df


# 东方财富-德国-经济数据-消费者物价指数月率终值
def macro_germany_cpi_monthly() -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-德国-消费者物价指数月率终值
    https://data.eastmoney.com/cjsj/foreign_1_1.html
    :return: 消费者物价指数月率终值
    :rtype: pandas.DataFrame
    """
    temp_df = macro_germany_core(symbol="EMG00009758")
    return temp_df


# 东方财富-德国-经济数据-消费者物价指数年率终值
def macro_germany_cpi_yearly() -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-德国-消费者物价指数年率终值
    https://data.eastmoney.com/cjsj/foreign_1_2.html
    :return: 消费者物价指数年率终值
    :rtype: pandas.DataFrame
    """
    temp_df = macro_germany_core(symbol="EMG00009756")
    return temp_df


# 东方财富-德国-经济数据-贸易帐(季调后)
def macro_germany_trade_adjusted() -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-德国-贸易帐(季调后)
    https://data.eastmoney.com/cjsj/foreign_1_3.html
    :return: 贸易帐(季调后)
    :rtype: pandas.DataFrame
    """
    temp_df = macro_germany_core(symbol="EMG00009753")
    return temp_df


# 东方财富-德国-经济数据-GDP
def macro_germany_gdp() -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-德国-GDP
    https://data.eastmoney.com/cjsj/foreign_1_4.html
    :return: GDP
    :rtype: pandas.DataFrame
    """
    temp_df = macro_germany_core(symbol="EMG00009720")
    return temp_df


# 东方财富-德国-经济数据-实际零售销售月率
def macro_germany_retail_sale_monthly() -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-德国-实际零售销售月率
    https://data.eastmoney.com/cjsj/foreign_1_5.html
    :return: 实际零售销售月率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_germany_core(symbol="EMG01333186")
    return temp_df


# 东方财富-德国-经济数据-实际零售销售年率
def macro_germany_retail_sale_yearly() -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-德国-实际零售销售年率
    https://data.eastmoney.com/cjsj/foreign_1_6.html
    :return: 实际零售销售年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_germany_core(symbol="EMG01333192")
    return temp_df


# 东方财富-德国-经济数据-ZEW 经济景气指数
def macro_germany_zew() -> pd.DataFrame:
    """
    东方财富-数据中心-经济数据一览-德国-ZEW 经济景气指数
    https://data.eastmoney.com/cjsj/foreign_1_7.html
    :return: ZEW 经济景气指数
    :rtype: pandas.DataFrame
    """
    temp_df = macro_germany_core(symbol="EMG00172577")
    return temp_df


if __name__ == "__main__":
    macro_germany_ifo_df = macro_germany_ifo()
    print(macro_germany_ifo_df)

    macro_germany_cpi_monthly_df = macro_germany_cpi_monthly()
    print(macro_germany_cpi_monthly_df)

    macro_germany_cpi_yearly_df = macro_germany_cpi_yearly()
    print(macro_germany_cpi_yearly_df)

    macro_germany_trade_adjusted_df = macro_germany_trade_adjusted()
    print(macro_germany_trade_adjusted_df)

    macro_germany_gdp_df = macro_germany_gdp()
    print(macro_germany_gdp_df)

    macro_germany_retail_sale_monthly_df = macro_germany_retail_sale_monthly()
    print(macro_germany_retail_sale_monthly_df)

    macro_germany_retail_sale_yearly_df = macro_germany_retail_sale_yearly()
    print(macro_germany_retail_sale_yearly_df)

    macro_germany_zew_df = macro_germany_zew()
    print(macro_germany_zew_df)
