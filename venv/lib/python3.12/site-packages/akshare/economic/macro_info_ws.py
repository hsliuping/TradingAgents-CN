#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/15 18:20
Desc: 华尔街见闻-日历-宏观
https://wallstreetcn.com/calendar
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests


def __convert_date_format(date: str) -> str:
    """
    将日期字符串从格式'%Y%m%d'转换为格式'%Y-%m-%d %H:%M:%S'。

    :param date: 日期字符串,格式为'%Y%m%d'
    :return: 转换后的日期字符串,格式为'%Y-%m-%d %H:%M:%S'
    """
    datetime_obj = datetime.strptime(date, "%Y%m%d")
    return datetime_obj.strftime("%Y-%m-%d %H:%M:%S")


def __format_date(date: str) -> int:
    """
    将日期字符串转换为Unix时间戳。

    :param date: 日期字符串,格式为'%Y-%m-%d %H:%M:%S'
    :return: Unix时间戳
    """
    datetime_obj = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
    return int(datetime_obj.timestamp())


def macro_info_ws(date: str = "20240514") -> pd.DataFrame:
    """
    华尔街见闻-日历-宏观
    https://wallstreetcn.com/calendar
    :param date: 日期
    :type date: str
    :return: 日历-宏观
    :rtype: pandas.DataFrame
    """
    date = __convert_date_format(date)
    url = "https://api-one-wscn.awtmt.com/apiv1/finance/macrodatas"
    datetime_obj = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
    one_day = timedelta(days=1)
    new_datetime = datetime_obj + one_day
    date_str = new_datetime.strftime("%Y-%m-%d %H:%M:%S")
    params = {"start": __format_date(date), "end": __format_date(date_str)}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["items"])
    temp_df["public_date"] = pd.to_datetime(
        temp_df["public_date"], errors="coerce", unit="s", utc=True
    ).dt.tz_convert("Asia/Shanghai")
    temp_df["public_date"] = temp_df["public_date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    temp_df = temp_df.rename(
        columns={
            "public_date": "时间",
            "country": "地区",
            "title": "事件",
            "importance": "重要性",
            "actual": "今值",
            "forecast": "预期",
            "previous": "前值",
            "revised": "修正",
            "uri": "链接",
        }
    )
    temp_df = temp_df[
        [
            "时间",
            "地区",
            "事件",
            "重要性",
            "今值",
            "预期",
            "前值",
            "修正",
            "链接",
        ]
    ]
    temp_df["今值"] = pd.to_numeric(temp_df["今值"], errors="coerce")
    temp_df["预期"] = pd.to_numeric(temp_df["预期"], errors="coerce")
    temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
    temp_df["修正"] = pd.to_numeric(temp_df["修正"], errors="coerce")
    temp_df["前值"] = np.where(
        temp_df["修正"].notnull(), temp_df["修正"], temp_df["前值"]
    )
    del temp_df["修正"]
    return temp_df


if __name__ == "__main__":
    macro_info_ws_df = macro_info_ws(date="20240514")
    print(macro_info_ws_df)
