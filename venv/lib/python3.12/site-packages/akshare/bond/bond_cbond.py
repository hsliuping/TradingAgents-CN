# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2022/9/20 17:46
Desc: 中国债券信息网-中债指数-中债指数族系-总指数-综合类指数
"""

import pandas as pd
import requests


def bond_new_composite_index_cbond(
    indicator: str = "财富", period: str = "总值"
) -> pd.DataFrame:
    """
    中国债券信息网-中债指数-中债指数族系-总指数-综合类指数-中债-新综合指数
    https://yield.chinabond.com.cn/cbweb-mn/indices/single_index_query
    :param indicator: choice of {"全价", "净价", "财富", "平均市值法久期", "平均现金流法久期", "平均市值法凸性", "平均现金流法凸性", "平均现金流法到期收益率", "平均市值法到期收益率", "平均基点价值", "平均待偿期", "平均派息率", "指数上日总市值", "财富指数涨跌幅", "全价指数涨跌幅", "净价指数涨跌幅", "现券结算量"}
    :type indicator: str
    :param period: choice of {"总值", "1年以下", "1-3年", "3-5年", "5-7年", "7-10年", "10年以上", "0-3个月", "3-6个月", "6-9个月", "9-12个月", "0-6个月", "6-12个月"}
    :type period: str
    :return: 新综合指数
    :rtype: pandas.DataFrame
    """
    indicator_map = {
        "全价": "QJZS",
        "净价": "JJZS",
        "财富": "CFZS",
        "平均市值法久期": "PJSZFJQ",
        "平均现金流法久期": "PJXJLFJQ",
        "平均市值法凸性": "PJSZFTX",
        "平均现金流法凸性": "PJXJLFTX",
        "平均现金流法到期收益率": "PJDQSYL",
        "平均市值法到期收益率": "PJSZFDQSYL",
        "平均基点价值": "PJJDJZ",
        "平均待偿期": "PJDCQ",
        "平均派息率": "PJPXL",
        "指数上日总市值": "ZSZSZ",
        "财富指数涨跌幅": "CFZSZDF",
        "全价指数涨跌幅": "QJZSZDF",
        "净价指数涨跌幅": "JJZSZDF",
        "现券结算量": "XQJSL",
    }
    period_map = {
        "总值": "00",
        "1年以下": "01",
        "1-3年": "02",
        "3-5年": "03",
        "5-7年": "04",
        "7-10年": "05",
        "10年以上": "06",
        "0-3个月": "07",
        "3-6个月": "08",
        "6-9个月": "09",
        "9-12个月": "10",
        "0-6个月": "11",
        "6-12个月": "12",
    }
    url = "https://yield.chinabond.com.cn/cbweb-mn/indices/singleIndexQuery"
    params = {
        "indexid": "8a8b2ca0332abed20134ea76d8885831",
        "": "",  # noqa: F601
        "qxlxt": period_map[period],
        "": "",  # noqa: F601
        "ltcslx": "",
        "": "",  # noqa: F601
        "zslxt": indicator_map[indicator],  # noqa: F601
        "": "",  # noqa: F601
        "zslxt": indicator_map[indicator],  # noqa: F601
        "": "",  # noqa: F601
        "lx": "1",
        "": "",  # noqa: F601
        "locale": "",
    }
    r = requests.post(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame.from_dict(
        data_json[f"{indicator_map[indicator]}_{period_map[period]}"],
        orient="index",
    )
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["date", "value"]
    temp_df["date"] = temp_df["date"].astype(float)
    temp_df["date"] = (
        pd.to_datetime(temp_df["date"], unit="ms", errors="coerce", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
    return temp_df


def bond_composite_index_cbond(
    indicator: str = "财富", period: str = "总值"
) -> pd.DataFrame:
    """
    中国债券信息网-中债指数-中债指数族系-总指数-综合类指数-中债-综合指数
    https://yield.chinabond.com.cn/cbweb-mn/indices/single_index_query
    :param indicator: choice of {"全价", "净价", "财富", "平均市值法久期", "平均现金流法久期", "平均市值法凸性", "平均现金流法凸性", "平均现金流法到期收益率", "平均市值法到期收益率", "平均基点价值", "平均待偿期", "平均派息率", "指数上日总市值", "财富指数涨跌幅", "全价指数涨跌幅", "净价指数涨跌幅", "现券结算量"}
    :type indicator: str
    :param period: choice of {"总值", "1年以下", "1-3年", "3-5年", "5-7年", "7-10年", "10年以上", "0-3个月", "3-6个月", "6-9个月", "9-12个月", "0-6个月", "6-12个月"}
    :type period: str
    :return: 新综合指数
    :rtype: pandas.DataFrame
    """
    indicator_map = {
        "全价": "QJZS",
        "净价": "JJZS",
        "财富": "CFZS",
        "平均市值法久期": "PJSZFJQ",
        "平均现金流法久期": "PJXJLFJQ",
        "平均市值法凸性": "PJSZFTX",
        "平均现金流法凸性": "PJXJLFTX",
        "平均现金流法到期收益率": "PJDQSYL",
        "平均市值法到期收益率": "PJSZFDQSYL",
        "平均基点价值": "PJJDJZ",
        "平均待偿期": "PJDCQ",
        "平均派息率": "PJPXL",
        "指数上日总市值": "ZSZSZ",
        "财富指数涨跌幅": "CFZSZDF",
        "全价指数涨跌幅": "QJZSZDF",
        "净价指数涨跌幅": "JJZSZDF",
        "现券结算量": "XQJSL",
    }
    period_map = {
        "总值": "00",
        "1年以下": "01",
        "1-3年": "02",
        "3-5年": "03",
        "5-7年": "04",
        "7-10年": "05",
        "10年以上": "06",
        "0-3个月": "07",
        "3-6个月": "08",
        "6-9个月": "09",
        "9-12个月": "10",
        "0-6个月": "11",
        "6-12个月": "12",
    }
    url = "https://yield.chinabond.com.cn/cbweb-mn/indices/singleIndexQuery"
    params = {
        "indexid": "2c90818811afed8d0111c0c672b31578",
        "": "",  # noqa: F601
        "qxlxt": period_map[period],
        "": "",  # noqa: F601
        "zslxt": indicator_map[indicator],
        "": "",  # noqa: F601
        "lx": "1",
        "": "",  # noqa: F601
        "locale": "",
    }
    r = requests.post(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame.from_dict(
        data_json[f"{indicator_map[indicator]}_{period_map[period]}"],
        orient="index",
    )
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["date", "value"]
    temp_df["date"] = pd.to_datetime(temp_df["date"], unit="ms").dt.date
    temp_df["value"] = pd.to_numeric(temp_df["value"])
    return temp_df


if __name__ == "__main__":
    bond_new_composite_index_cbond_df = bond_new_composite_index_cbond(
        indicator="财富", period="总值"
    )
    print(bond_new_composite_index_cbond_df)

    bond_composite_index_cbond_df = bond_composite_index_cbond(
        indicator="财富", period="总值"
    )
    print(bond_composite_index_cbond_df)
