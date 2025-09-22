#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/3 16:21
Desc: 中国-香港-宏观指标
https://data.eastmoney.com/cjsj/foreign_8_0.html
"""

import pandas as pd
import requests


def macro_china_hk_core(symbol: str = "EMG00341602") -> pd.DataFrame:
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
        "reportName": "RPT_ECONOMICVALUE_HK",
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


def macro_china_hk_cpi() -> pd.DataFrame:
    """
    东方财富-经济数据一览-中国香港-消费者物价指数
    https://data.eastmoney.com/cjsj/foreign_8_0.html
    :return: 消费者物价指数
    :rtype: pandas.DataFrame
    """
    temp_df = macro_china_hk_core(symbol="EMG01336996")
    return temp_df


def macro_china_hk_cpi_ratio() -> pd.DataFrame:
    """
    东方财富-经济数据一览-中国香港-消费者物价指数年率
    https://data.eastmoney.com/cjsj/foreign_8_1.html
    :return: 消费者物价指数年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_china_hk_core(symbol="EMG00059282")
    return temp_df


def macro_china_hk_rate_of_unemployment() -> pd.DataFrame:
    """
    东方财富-经济数据一览-中国香港-失业率
    https://data.eastmoney.com/cjsj/foreign_8_2.html
    :return: 失业率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_china_hk_core(symbol="EMG00059647")
    return temp_df


def macro_china_hk_gbp() -> pd.DataFrame:
    """
    东方财富-经济数据一览-中国香港-香港 GDP
    https://data.eastmoney.com/cjsj/foreign_8_3.html
    :return: 香港 GDP
    :rtype: pandas.DataFrame
    """
    temp_df = macro_china_hk_core(symbol="EMG01337008")
    return temp_df


def macro_china_hk_gbp_ratio() -> pd.DataFrame:
    """
    东方财富-经济数据一览-中国香港-香港 GDP 同比
    https://data.eastmoney.com/cjsj/foreign_8_4.html
    :return: 香港 GDP 同比
    :rtype: pandas.DataFrame
    """
    temp_df = macro_china_hk_core(symbol="EMG01337009")
    return temp_df


def macro_china_hk_building_volume() -> pd.DataFrame:
    """
    东方财富-经济数据一览-中国香港-香港楼宇买卖合约数量
    https://data.eastmoney.com/cjsj/foreign_8_5.html
    :return: 香港楼宇买卖合约数量
    :rtype: pandas.DataFrame
    """
    temp_df = macro_china_hk_core(symbol="EMG00158055")
    return temp_df


def macro_china_hk_building_amount() -> pd.DataFrame:
    """
    东方财富-经济数据一览-中国香港-香港楼宇买卖合约成交金额
    https://data.eastmoney.com/cjsj/foreign_8_6.html
    :return: 香港楼宇买卖合约成交金额
    :rtype: pandas.DataFrame
    """
    temp_df = macro_china_hk_core(symbol="EMG00158066")
    return temp_df


def macro_china_hk_trade_diff_ratio() -> pd.DataFrame:
    """
    东方财富-经济数据一览-中国香港-香港商品贸易差额年率
    https://data.eastmoney.com/cjsj/foreign_8_7.html
    :return: 香港商品贸易差额年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_china_hk_core(symbol="EMG00157898")
    return temp_df


def macro_china_hk_ppi() -> pd.DataFrame:
    """
    东方财富-经济数据一览-中国香港-香港制造业 PPI 年率
    https://data.eastmoney.com/cjsj/foreign_8_8.html
    :return: 香港制造业 PPI 年率
    :rtype: pandas.DataFrame
    """
    temp_df = macro_china_hk_core(symbol="EMG00157818")
    return temp_df


if __name__ == "__main__":
    macro_china_hk_cpi_df = macro_china_hk_cpi()
    print(macro_china_hk_cpi_df)

    macro_china_hk_cpi_ratio_df = macro_china_hk_cpi_ratio()
    print(macro_china_hk_cpi_ratio_df)

    macro_china_hk_rate_of_unemployment_df = macro_china_hk_rate_of_unemployment()
    print(macro_china_hk_rate_of_unemployment_df)

    macro_china_hk_gbp_df = macro_china_hk_gbp()
    print(macro_china_hk_gbp_df)

    macro_china_hk_gbp_ratio_df = macro_china_hk_gbp_ratio()
    print(macro_china_hk_gbp_ratio_df)

    marco_china_hk_building_volume_df = macro_china_hk_building_volume()
    print(marco_china_hk_building_volume_df)

    macro_china_hk_building_amount_df = macro_china_hk_building_amount()
    print(macro_china_hk_building_amount_df)

    macro_china_hk_trade_diff_ratio_df = macro_china_hk_trade_diff_ratio()
    print(macro_china_hk_trade_diff_ratio_df)

    macro_china_hk_ppi_df = macro_china_hk_ppi()
    print(macro_china_hk_ppi_df)
