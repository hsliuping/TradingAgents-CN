#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/29 16:00
Desc: 日出和日落数据
https://www.timeanddate.com
"""

from io import StringIO

import pandas as pd
import requests


def sunrise_city_list() -> list:
    """
    查询日出与日落数据的城市列表
    https://www.timeanddate.com/astronomy/china
    :return: 所有可以获取的数据的城市列表
    :rtype: list
    """
    url = "https://www.timeanddate.com/astronomy/china"
    r = requests.get(url)
    city_list = []
    china_city_one_df = pd.read_html(StringIO(r.text))[1]
    china_city_two_df = pd.read_html(StringIO(r.text))[2]
    city_list.extend([item.lower() for item in china_city_one_df.iloc[:, 0].tolist()])
    city_list.extend([item.lower() for item in china_city_one_df.iloc[:, 3].tolist()])
    city_list.extend([item.lower() for item in china_city_one_df.iloc[:, 6].tolist()])
    city_list.extend([item.lower() for item in china_city_two_df.iloc[:, 0].tolist()])
    city_list.extend([item.lower() for item in china_city_two_df.iloc[:, 1].tolist()])
    city_list.extend([item.lower() for item in china_city_two_df.iloc[:, 2].tolist()])
    city_list.extend([item.lower() for item in china_city_two_df.iloc[:, 3].tolist()])
    city_list.extend(
        [item.lower() for item in china_city_two_df.iloc[:, 4].dropna().tolist()]
    )
    return city_list


def sunrise_daily(date: str = "20240428", city: str = "beijing") -> pd.DataFrame:
    """
    每日日出日落数据
    https://www.timeanddate.com/astronomy/china/shaoxing
    :param date: 需要查询的日期, e.g., “20200428”
    :type date: str
    :param city: 需要查询的城市; 注意输入的格式, e.g., "北京", "上海"
    :type city: str
    :return: 返回指定日期指定地区的日出日落数据
    :rtype: pandas.DataFrame
    """
    import urllib3

    urllib3.disable_warnings()
    if city in sunrise_city_list():
        year = date[:4]
        month = date[4:6]
        url = f"https://www.timeanddate.com/sun/china/{city}?month={month}&year={year}"
        r = requests.get(url, verify=False)
        table = pd.read_html(StringIO(r.text), header=2)[1]
        month_df = table.iloc[:-1,]
        day_df = month_df[
            month_df.iloc[:, 0].astype(str).str.zfill(2) == date[6:]
        ].copy()
        day_df.index = pd.to_datetime([date] * len(day_df), format="%Y%m%d")
        day_df.reset_index(inplace=True)
        day_df.rename(columns={"index": "date"}, inplace=True)
        day_df["date"] = pd.to_datetime(day_df["date"]).dt.date
        return day_df
    else:
        raise "请输入正确的城市名称"


def sunrise_monthly(date: str = "20240428", city: str = "beijing") -> pd.DataFrame:
    """
    每个指定 date 所在月份的每日日出日落数据, 如果当前月份未到月底, 则以预测值填充
    https://www.timeanddate.com/astronomy/china/shaoxing
    :param date: 需要查询的日期, 这里用来指定 date 所在的月份; e.g., “20200428”
    :type date: str
    :param city: 需要查询的城市; 注意输入的格式, e.g., "北京", "上海"
    :type city: str
    :return: 指定 date 所在月份的每日日出日落数据
    :rtype: pandas.DataFrame
    """
    import urllib3

    urllib3.disable_warnings()
    if city in sunrise_city_list():
        year = date[:4]
        month = date[4:6]
        url = f"https://www.timeanddate.com/sun/china/{city}?month={month}&year={year}"
        r = requests.get(url)
        table = pd.read_html(StringIO(r.text), header=2)[1]
        month_df = table.iloc[:-1,].copy()
        month_df.index = [date[:-2]] * len(month_df)
        month_df.reset_index(inplace=True)
        month_df.rename(
            columns={
                "index": "date",
            },
            inplace=True,
        )
        return month_df
    else:
        raise "请输入正确的城市名称"


if __name__ == "__main__":
    sunrise_daily_df = sunrise_daily(date="20240428", city="beijing")
    print(sunrise_daily_df)

    sunrise_monthly_df = sunrise_monthly(date="20240428", city="beijing")
    print(sunrise_monthly_df)
