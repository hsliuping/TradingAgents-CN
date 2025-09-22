# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2025/3/7 20:30
Desc: 百度股市通-经济数据
https://gushitong.baidu.com/calendar
"""

import pandas as pd
import requests


def news_economic_baidu(date: str = "20241107") -> pd.DataFrame:
    """
    百度股市通-经济数据
    https://gushitong.baidu.com/calendar
    :param date: 查询日期
    :type date: str
    :return: 经济数据
    :rtype: pandas.DataFrame
    """
    start_date = "-".join([date[:4], date[4:6], date[6:]])
    end_date = "-".join([date[:4], date[4:6], date[6:]])
    url = "https://finance.pae.baidu.com/api/financecalendar"
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "market": "",
        "cate": "economic_data",
        "finClientType": "pc",
    }
    r = requests.get(url=url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    for item in data_json["Result"]:
        if not item["list"] == []:
            temp_df = pd.DataFrame(item["list"])
            temp_df.columns = [
                "日期",
                "时间",
                "-",
                "事件",
                "重要性",
                "前值",
                "预期",
                "公布",
                "-",
                "-",
                "地区",
                "-",
            ]
            temp_df = temp_df[
                [
                    "日期",
                    "时间",
                    "地区",
                    "事件",
                    "公布",
                    "预期",
                    "前值",
                    "重要性",
                ]
            ]
            temp_df["公布"] = pd.to_numeric(temp_df["公布"], errors="coerce")
            temp_df["预期"] = pd.to_numeric(temp_df["预期"], errors="coerce")
            temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
            temp_df["重要性"] = pd.to_numeric(temp_df["重要性"], errors="coerce")
            temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
        else:
            continue
    return big_df


def news_trade_notify_suspend_baidu(date: str = "20241107") -> pd.DataFrame:
    """
    百度股市通-交易提醒-停复牌
    https://gushitong.baidu.com/calendar
    :param date: 查询日期
    :type date: str
    :return: 交易提醒-停复牌
    :rtype: pandas.DataFrame
    """
    start_date = "-".join([date[:4], date[4:6], date[6:]])
    end_date = "-".join([date[:4], date[4:6], date[6:]])
    url = "https://finance.pae.baidu.com/api/financecalendar"
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "market": "",
        "cate": "notify_suspend",
        "finClientType": "pc",
    }
    r = requests.get(url=url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    for item in data_json["Result"]:
        if not item["list"] == []:
            temp_df = pd.DataFrame(item["list"])
            temp_df.columns = [
                "股票代码",
                "-",
                "交易所",
                "股票简称",
                "停牌时间",
                "复牌时间",
                "-",
                "停牌事项说明",
            ]
            temp_df = temp_df[
                [
                    "股票代码",
                    "股票简称",
                    "交易所",
                    "停牌时间",
                    "复牌时间",
                    "停牌事项说明",
                ]
            ]
            temp_df["停牌时间"] = pd.to_datetime(
                temp_df["停牌时间"], errors="coerce"
            ).dt.date
            temp_df["复牌时间"] = pd.to_datetime(
                temp_df["复牌时间"], errors="coerce"
            ).dt.date
            big_df = pd.concat([big_df, temp_df], ignore_index=True)
        else:
            continue
    return big_df


def news_trade_notify_dividend_baidu(date: str = "20241107") -> pd.DataFrame:
    """
    百度股市通-交易提醒-分红派息
    https://gushitong.baidu.com/calendar
    :param date: 查询日期
    :type date: str
    :return: 交易提醒-分红派息
    :rtype: pandas.DataFrame
    """
    start_date = "-".join([date[:4], date[4:6], date[6:]])
    end_date = "-".join([date[:4], date[4:6], date[6:]])
    url = "https://finance.pae.baidu.com/api/financecalendar"
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "market": "",
        "cate": "notify_divide",
        "rn": 500,
        "pn": 0,
    }
    r = requests.get(url=url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    for item in data_json["Result"]:
        if not item["list"] == []:
            temp_df = pd.DataFrame(item["list"])
            temp_df.rename(
                columns={
                    "code": "股票代码",
                    "market": "-",
                    "exchange": "交易所",
                    "name": "股票简称",
                    "diviDate": "除权日",
                    "date": "报告期",
                    "diviCash": "分红",
                    "shareDivide": "送股",
                    "transfer": "转增",
                    "physical": "实物",
                },
                inplace=True,
            )
            if "实物" not in temp_df.columns:
                temp_df["实物"] = pd.NA
            temp_df = temp_df[
                [
                    "股票代码",
                    "除权日",
                    "分红",
                    "送股",
                    "转增",
                    "实物",
                    "交易所",
                    "股票简称",
                    "报告期",
                ]
            ]
            temp_df["除权日"] = pd.to_datetime(
                temp_df["除权日"], errors="coerce"
            ).dt.date
            temp_df["报告期"] = pd.to_datetime(
                temp_df["报告期"], errors="coerce"
            ).dt.date
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
        else:
            continue
    return big_df


def news_report_time_baidu(date: str = "20241107") -> pd.DataFrame:
    """
    百度股市通-财报发行
    https://gushitong.baidu.com/calendar
    :param date: 查询日期
    :type date: str
    :return: 财报发行
    :rtype: pandas.DataFrame
    """
    start_date = "-".join([date[:4], date[4:6], date[6:]])
    end_date = "-".join([date[:4], date[4:6], date[6:]])
    url = "https://finance.pae.baidu.com/api/financecalendar"
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "market": "",
        "cate": "report_time",
        "finClientType": "pc",
    }
    r = requests.get(url=url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    for item in data_json["Result"]:
        if not item["list"] == []:
            temp_df = pd.DataFrame(item["list"])
            temp_df.columns = [
                "股票代码",
                "-",
                "交易所",
                "-",
                "股票简称",
                "-",
                "财报期",
            ]
            temp_df = temp_df[
                [
                    "股票代码",
                    "交易所",
                    "股票简称",
                    "财报期",
                ]
            ]
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
        else:
            continue
    return big_df


if __name__ == "__main__":
    news_economic_baidu_df = news_economic_baidu(date="20250307")
    print(news_economic_baidu_df)

    news_trade_notify_suspend_baidu_df = news_trade_notify_suspend_baidu(
        date="20241107"
    )
    print(news_trade_notify_suspend_baidu_df)

    news_trade_notify_dividend_baidu_df = news_trade_notify_dividend_baidu(
        date="20250506"
    )
    print(news_trade_notify_dividend_baidu_df)

    news_report_time_baidu_df = news_report_time_baidu(date="20241107")
    print(news_report_time_baidu_df)
