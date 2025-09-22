#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/2/20 14:00
Desc: 电影票房数据
https://ys.endata.cn/BoxOffice/Movie
"""

import datetime
import json
import os

import pandas as pd
import requests
import py_mini_racer


def _get_js_path(name: str = "", module_file: str = "") -> str:
    """
    get JS file path
    :param name: file name
    :type name: str
    :param module_file: filename
    :type module_file: str
    :return: 路径
    :rtype: str
    """
    module_folder = os.path.abspath(os.path.dirname(os.path.dirname(module_file)))
    module_json_path = os.path.join(module_folder, "movie", name)
    return module_json_path


def _get_file_content(file_name: str = "jm.js"):
    """
    read the file content
    :param file_name: filename
    :type file_name: str
    :return: file content
    :rtype: str
    """
    setting_file_name = file_name
    setting_file_path = _get_js_path(setting_file_name, __file__)
    with open(setting_file_path) as f:
        file_data = f.read()
    return file_data


def get_current_week(date: str = "20201019") -> datetime.date:
    """
    当前周的周一
    :param date: 具体的日期
    :type date: str
    :return: 当前周的周一
    :rtype: datetime.date
    """
    monday = datetime.datetime.strptime(date, "%Y%m%d").date()
    one_day = datetime.timedelta(days=1)
    while monday.weekday() != 0:
        monday -= one_day
    return monday


def decrypt(origin_data: str = "") -> str:
    """
    解密
    :param origin_data: 解密前的字符串
    :type origin_data: str
    :return: 解密后的字符串
    :rtype: str
    """
    file_data = _get_file_content(file_name="jm.js")
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(file_data)
    data = ctx.call("webInstace.shell", origin_data)
    return data


def movie_boxoffice_realtime() -> pd.DataFrame:
    """
    电影票房-实时票房
    https://ys.endata.cn/BoxOffice/Movie
    :return: 实时票房数据
    :rtype: pandas.DataFrame
    """
    today = datetime.datetime.today().date().strftime("%Y%m%d")
    url = "https://www.endata.com.cn/API/GetData.ashx"
    payload = {
        "showDate": "",
        "tdate": f"{today[:4]}-{today[4:6]}-{today[6:]}",
        "MethodName": "BoxOffice_GetHourBoxOffice",
    }
    r = requests.post(url, data=payload)
    r.encoding = "utf8"
    data_json = json.loads(decrypt(r.text))
    temp_df = pd.DataFrame(data_json["Data"]["Table1"])
    temp_df = temp_df.iloc[:, :7]
    temp_df.columns = [
        "排序",
        "_",
        "影片名称",
        "实时票房",
        "累计票房",
        "上映天数",
        "票房占比",
    ]
    temp_df = temp_df[
        ["排序", "影片名称", "实时票房", "票房占比", "上映天数", "累计票房"]
    ]
    return temp_df


def movie_boxoffice_daily(date: str = "20240219") -> pd.DataFrame:
    """
    电影票房-单日票房
    https://www.endata.com.cn/BoxOffice/BO/Day/index.html
    :param date: 只能设置当前日期的前一天的票房数据
    :type date: str
    :return: 每日票房
    :rtype: pandas.DataFrame
    """
    last_date = datetime.datetime.strptime(date, "%Y%m%d") - datetime.timedelta(days=1)
    last_date = last_date.strftime("%Y%m%d")
    url = "https://www.endata.com.cn/API/GetData.ashx"
    payload = {
        "sdate": f"{date[:4]}-{date[4:6]}-{date[6:]}",
        "edate": f"{last_date[:4]}-{last_date[4:6]}-{last_date[6:]}",
        "MethodName": "BoxOffice_GetDayBoxOffice",
    }
    r = requests.post(url, data=payload)
    r.encoding = "utf8"
    data_json = json.loads(decrypt(r.text))
    temp_df = pd.DataFrame(data_json["Data"]["Table"])
    temp_df.columns = [
        "排序",
        "_",
        "影片名称",
        "_",
        "累计票房",
        "平均票价",
        "上映天数",
        "场均人次",
        "_",
        "_",
        "_",
        "_",
        "_",
        "单日票房",
        "环比变化",
        "_",
        "口碑指数",
    ]
    temp_df = temp_df[
        [
            "排序",
            "影片名称",
            "单日票房",
            "环比变化",
            "累计票房",
            "平均票价",
            "场均人次",
            "口碑指数",
            "上映天数",
        ]
    ]
    return temp_df


def movie_boxoffice_weekly(date: str = "20240218") -> pd.DataFrame:
    """
    电影票房-单周票房
    https://www.endata.com.cn/BoxOffice/BO/Week/oneWeek.html
    :param date: 只能获取指定日期所在完整周的票房数据
    :type date: str
    :return: 单周票房
    :rtype: pandas.DataFrame
    """
    url = "https://www.endata.com.cn/API/GetData.ashx"
    payload = {
        "sdate": get_current_week(date=date).strftime("%Y-%m-%d"),
        "MethodName": "BoxOffice_GetWeekInfoData",
    }
    r = requests.post(url, data=payload)
    data_json = json.loads(decrypt(r.text))
    temp_df = pd.DataFrame(data_json["Data"]["Table"])
    temp_df.columns = [
        "排序",
        "_",
        "影片名称",
        "单周票房",
        "累计票房",
        "_",
        "上映天数",
        "平均票价",
        "场均人次",
        "环比变化",
        "_",
        "_",
        "_",
        "排名变化",
        "口碑指数",
    ]
    temp_df = temp_df[
        [
            "排序",
            "影片名称",
            "排名变化",
            "单周票房",
            "环比变化",
            "累计票房",
            "平均票价",
            "场均人次",
            "口碑指数",
            "上映天数",
        ]
    ]
    temp_df["单周票房"] = pd.to_numeric(temp_df["单周票房"], errors="coerce")
    temp_df["环比变化"] = pd.to_numeric(temp_df["环比变化"], errors="coerce")
    temp_df["累计票房"] = pd.to_numeric(temp_df["累计票房"], errors="coerce")
    return temp_df


def movie_boxoffice_monthly(date: str = "20240218") -> pd.DataFrame:
    """
    电影票房-单月票房
    https://www.endata.com.cn/BoxOffice/BO/Month/oneMonth.html
    :param date: 指定日期所在月份的月度票房
    :type date: str
    :return: 单月票房
    :rtype: pandas.DataFrame
    """
    url = "https://www.endata.com.cn/API/GetData.ashx"
    payload = {
        "startTime": f"{date[:4]}-{date[4:6]}-01",
        "MethodName": "BoxOffice_GetMonthBox",
    }
    r = requests.post(url, data=payload)
    r.encoding = "utf8"
    data_json = json.loads(decrypt(r.text))
    temp_df = pd.DataFrame(data_json["Data"]["Table"])
    temp_df.columns = [
        "排序",
        "_",
        "影片名称",
        "月内天数",
        "单月票房",
        "平均票价",
        "场均人次",
        "月度占比",
        "上映日期",
        "_",
        "口碑指数",
    ]
    temp_df = temp_df[
        [
            "排序",
            "影片名称",
            "单月票房",
            "月度占比",
            "平均票价",
            "场均人次",
            "上映日期",
            "口碑指数",
            "月内天数",
        ]
    ]
    temp_df["上映日期"] = pd.to_datetime(temp_df["上映日期"], errors="coerce").dt.date
    return temp_df


def movie_boxoffice_yearly(date: str = "20240218") -> pd.DataFrame:
    """
    电影票房-年度票房
    https://www.endata.com.cn/BoxOffice/BO/Year/index.html
    :param date: 当前日期所在年度的票房数据
    :type date: str
    :return: 年度票房
    :rtype: pandas.DataFrame
    """
    url = "https://www.endata.com.cn/API/GetData.ashx"
    payload = {
        "year": f"{date[:4]}",
        "MethodName": "BoxOffice_GetYearInfoData",
    }
    r = requests.post(url, data=payload)
    r.encoding = "utf8"
    data_json = json.loads(decrypt(r.text))
    temp_df = pd.DataFrame(data_json["Data"]["Table"])
    temp_df.reset_index(inplace=True)
    temp_df.columns = [
        "排序",
        "_",
        "影片名称",
        "类型",
        "总票房",
        "平均票价",
        "场均人次",
        "国家及地区",
        "上映日期",
        "_",
    ]
    temp_df["排序"] = range(1, len(temp_df) + 1)
    temp_df = temp_df[
        [
            "排序",
            "影片名称",
            "类型",
            "总票房",
            "平均票价",
            "场均人次",
            "国家及地区",
            "上映日期",
        ]
    ]
    temp_df["上映日期"] = pd.to_datetime(temp_df["上映日期"], errors="coerce").dt.date
    return temp_df


def movie_boxoffice_yearly_first_week(date: str = "20201018") -> pd.DataFrame:
    """
    电影票房-年度票房-年度首周票房
    https://www.endata.com.cn/BoxOffice/BO/Year/firstWeek.html
    :param date: 当前日期所在年度的年度首周票房票房数据
    :type date: str
    :return: 年度首周票房
    :rtype: pandas.DataFrame
    """
    url = "https://www.endata.com.cn/API/GetData.ashx"
    payload = {
        "year": f"{date[:4]}",
        "MethodName": "BoxOffice_getYearInfo_fData",
    }
    r = requests.post(url, data=payload)
    r.encoding = "utf8"
    data_json = json.loads(decrypt(r.text))
    temp_df = pd.DataFrame(data_json["Data"]["Table"])
    temp_df.reset_index(inplace=True)
    temp_df.columns = [
        "排序",
        "_",
        "_",
        "影片名称",
        "首周票房",
        "场均人次",
        "上映日期",
        "首周天数",
        "类型",
        "国家及地区",
        "_",
        "占总票房比重",
    ]
    temp_df["排序"] = range(1, len(temp_df) + 1)
    temp_df = temp_df[
        [
            "排序",
            "影片名称",
            "类型",
            "首周票房",
            "占总票房比重",
            "场均人次",
            "国家及地区",
            "上映日期",
            "首周天数",
        ]
    ]
    temp_df["上映日期"] = pd.to_datetime(temp_df["上映日期"], errors="coerce").dt.date
    return temp_df


def movie_boxoffice_cinema_daily(date: str = "20240219") -> pd.DataFrame:
    """
    电影票房-影院票房-日票房排行
    https://www.endata.com.cn/BoxOffice/BO/Cinema/day.html
    :param date: 当前日期前一日的票房数据
    :type date: str
    :return: 影票房-影院票房-日票房排行
    :rtype: pandas.DataFrame
    """
    url = "https://www.endata.com.cn/API/GetData.ashx"
    payload = {
        "rowNum1": "1",
        "rowNum2": "100",
        "date": date,
        "MethodName": "BoxOffice_GetCinemaDayBoxOffice",
    }
    r = requests.post(url, data=payload)
    r.encoding = "utf8"
    data_json = json.loads(decrypt(r.text))
    temp_df = pd.DataFrame(data_json["Data"]["Table"])
    temp_df.columns = [
        "排序",
        "_",
        "影院名称",
        "单日票房",
        "单日场次",
        "_",
        "_",
        "场均票价",
        "场均人次",
        "上座率",
    ]
    temp_df = temp_df[
        ["排序", "影院名称", "单日票房", "单日场次", "场均人次", "场均票价", "上座率"]
    ]
    return temp_df


def movie_boxoffice_cinema_weekly(date: str = "20240219") -> pd.DataFrame:
    """
    电影票房-影院票房-周票房排行
    https://www.endata.com.cn/BoxOffice/BO/Cinema/week.html
    :param date: 当前日期前完整一周的票房数据
    :type date: str
    :return: 影票房-影院票房-轴票房排行
    :rtype: pandas.DataFrame
    """
    url = "https://www.endata.com.cn/API/GetData.ashx"
    payload = {
        "dateID": str(
            datetime.date.fromisoformat(
                f"{date[:4]}-{date[4:6]}-{date[6:]}"
            ).isocalendar()[1]
            - 1
            - 41
            + 1128
        ),
        "rowNum1": "1",
        "rowNum2": "100",
        "MethodName": "BoxOffice_GetCinemaWeekBoxOffice",
    }
    r = requests.post(url, data=payload)
    r.encoding = "utf8"
    data_json = json.loads(decrypt(r.text))
    temp_df = pd.DataFrame(data_json["Data"]["Table"])
    temp_df.columns = [
        "排序",
        "_",
        "影院名称",
        "当周票房",
        "_",
        "单银幕票房",
        "场均人次",
        "单日单厅票房",
        "单日单厅场次",
    ]
    temp_df = temp_df[
        [
            "排序",
            "影院名称",
            "当周票房",
            "单银幕票房",
            "场均人次",
            "单日单厅票房",
            "单日单厅场次",
        ]
    ]
    return temp_df


if __name__ == "__main__":
    movie_boxoffice_realtime_df = movie_boxoffice_realtime()
    print(movie_boxoffice_realtime_df)

    movie_boxoffice_daily_df = movie_boxoffice_daily(date="20240219")
    print(movie_boxoffice_daily_df)

    movie_boxoffice_weekly_df = movie_boxoffice_weekly(date="20240218")
    print(movie_boxoffice_weekly_df)

    movie_boxoffice_monthly_df = movie_boxoffice_monthly(date="20240218")
    print(movie_boxoffice_monthly_df)

    movie_boxoffice_yearly_df = movie_boxoffice_yearly(date="20240218")
    print(movie_boxoffice_yearly_df)

    movie_boxoffice_yearly_first_week_df = movie_boxoffice_yearly_first_week(
        date="20201018"
    )
    print(movie_boxoffice_yearly_first_week_df)

    movie_boxoffice_cinema_daily_df = movie_boxoffice_cinema_daily(date="20240219")
    print(movie_boxoffice_cinema_daily_df)

    movie_boxoffice_cinema_weekly_df = movie_boxoffice_cinema_weekly(date="20240219")
    print(movie_boxoffice_cinema_weekly_df)
