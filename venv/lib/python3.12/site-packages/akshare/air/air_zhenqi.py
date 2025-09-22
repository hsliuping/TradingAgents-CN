#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/2 22:40
Desc: 真气网-空气质量
https://www.zq12369.com/environment.php
空气质量在线监测分析平台的空气质量数据
https://www.aqistudy.cn/
"""

import json
import os
import re
from io import StringIO

import pandas as pd
import requests
from py_mini_racer import MiniRacer

from akshare.utils import demjson


def _get_js_path(name: str = None, module_file: str = None) -> str:
    """
    获取 JS 文件的路径(从模块所在目录查找)
    :param name: 文件名
    :type name: str
    :param module_file: 模块路径
    :type module_file: str
    :return: 路径
    :rtype: str
    """
    module_folder = os.path.abspath(os.path.dirname(os.path.dirname(module_file)))
    module_json_path = os.path.join(module_folder, "air", name)
    return module_json_path


def _get_file_content(file_name: str = "crypto.js") -> str:
    """
    获取 JS 文件的内容
    :param file_name:  JS 文件名
    :type file_name: str
    :return: 文件内容
    :rtype: str
    """
    setting_file_name = file_name
    setting_file_path = _get_js_path(setting_file_name, __file__)
    with open(setting_file_path) as f:
        file_data = f.read()
    return file_data


def has_month_data(href):
    """
    Deal with href node
    :param href: href
    :type href: str
    :return: href result
    :rtype: str
    """
    return href and re.compile("monthdata.php").search(href)


def air_city_table() -> pd.DataFrame:
    """
    真气网-空气质量历史数据查询-全部城市列表
    https://www.zq12369.com/environment.php?date=2019-06-05&tab=rank&order=DESC&type=DAY#rank
    :return: 城市映射
    :rtype: pandas.DataFrame
    """
    url = "https://www.zq12369.com/environment.php"
    date = "2020-05-01"
    temp_df = None
    if len(date.split("-")) == 3:
        params = {
            "date": date,
            "tab": "rank",
            "order": "DESC",
            "type": "DAY",
        }
        r = requests.get(url, params=params)
        temp_df = pd.read_html(StringIO(r.text))[1].iloc[1:, :]
        del temp_df["降序"]
        temp_df.reset_index(inplace=True)
        temp_df["index"] = temp_df.index + 1
        temp_df.columns = [
            "序号",
            "省份",
            "城市",
            "AQI",
            "空气质量",
            "PM2.5浓度",
            "首要污染物",
        ]
        temp_df["AQI"] = pd.to_numeric(temp_df["AQI"])
    return temp_df


def air_quality_watch_point(
    city: str = "杭州", start_date: str = "20220408", end_date: str = "20220409"
) -> pd.DataFrame:
    """
    真气网-监测点空气质量-细化到具体城市的每个监测点
    指定之间段之间的空气质量数据
    https://www.zq12369.com/
    :param city: 调用 ak.air_city_table() 接口获取
    :type city: str
    :param start_date: e.g., "20190327"
    :type start_date: str
    :param end_date: e.g., ""20200327""
    :type end_date: str
    :return: 指定城市指定日期区间的观测点空气质量
    :rtype: pandas.DataFrame
    """
    start_date = "-".join([start_date[:4], start_date[4:6], start_date[6:]])
    end_date = "-".join([end_date[:4], end_date[4:6], end_date[6:]])
    url = "https://www.zq12369.com/api/zhenqiapi.php"
    file_data = _get_file_content(file_name="crypto.js")
    ctx = MiniRacer()
    ctx.eval(file_data)
    method = "GETCITYPOINTAVG"
    ctx.call("encode_param", method)
    ctx.call("encode_param", start_date)
    ctx.call("encode_param", end_date)
    city_param = ctx.call("encode_param", city)
    ctx.call("encode_secret", method, city_param, start_date, end_date)
    payload = {
        "appId": "a01901d3caba1f362d69474674ce477f",
        "method": ctx.call("encode_param", method),
        "city": city_param,
        "startTime": ctx.call("encode_param", start_date),
        "endTime": ctx.call("encode_param", end_date),
        "secret": ctx.call("encode_secret", method, city_param, start_date, end_date),
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.122 Safari/537.36"
    }
    r = requests.post(url, data=payload, headers=headers)
    data_text = r.text
    data_json = demjson.decode(ctx.call("decode_result", data_text))
    temp_df = pd.DataFrame(data_json["rows"])
    return temp_df


def air_quality_hist(
    city: str = "杭州",
    period: str = "day",
    start_date: str = "20190327",
    end_date: str = "20200427",
) -> pd.DataFrame:
    """
    真气网-空气历史数据
    https://www.zq12369.com/
    :param city: 调用 ak.air_city_table() 接口获取所有城市列表
    :type city: str
    :param period: "hour": 每小时一个数据, 由于数据量比较大, 下载较慢; "day": 每天一个数据; "month": 每个月一个数据
    :type period: str
    :param start_date: e.g., "20190327"
    :type start_date: str
    :param end_date: e.g., "20200327"
    :type end_date: str
    :return: 指定城市和数据频率下在指定时间段内的空气质量数据
    :rtype: pandas.DataFrame
    """
    start_date = "-".join([start_date[:4], start_date[4:6], start_date[6:]])
    end_date = "-".join([end_date[:4], end_date[4:6], end_date[6:]])
    url = "https://www.zq12369.com/api/newzhenqiapi.php"
    file_data = _get_file_content(file_name="outcrypto.js")
    ctx = MiniRacer()
    ctx.eval(file_data)
    app_id = "4f0e3a273d547ce6b7147bfa7ceb4b6e"
    method = "CETCITYPERIOD"
    timestamp = ctx.eval("timestamp = new Date().getTime()")
    p_text = json.dumps(
        {
            "city": city,
            "endTime": f"{end_date} 23:45:39",
            "startTime": f"{start_date} 00:00:00",
            "type": period.upper(),
        },
        ensure_ascii=False,
        indent=None,
    ).replace(' "', '"')
    secret = ctx.call("hex_md5", app_id + method + str(timestamp) + "WEB" + p_text)
    payload = {
        "appId": "4f0e3a273d547ce6b7147bfa7ceb4b6e",
        "method": "CETCITYPERIOD",
        "timestamp": int(timestamp),
        "clienttype": "WEB",
        "object": {
            "city": city,
            "type": period.upper(),
            "startTime": f"{start_date} 00:00:00",
            "endTime": f"{end_date} 23:45:39",
        },
        "secret": secret,
    }
    need = (
        json.dumps(payload, ensure_ascii=False, indent=None, sort_keys=False)
        .replace(' "', '"')
        .replace("\\", "")
        .replace('p": ', 'p":')
        .replace('t": ', 't":')
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        "Chrome/100.0.4896.75 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {"param": ctx.call("encode_param", need)}
    r = requests.post(url, data=params, headers=headers)
    temp_text = ctx.call("decryptData", r.text)
    data_json = demjson.decode(ctx.call("b.decode", temp_text))
    temp_df = pd.DataFrame(data_json["result"]["data"]["rows"])
    temp_df.index = temp_df["time"]
    del temp_df["time"]
    temp_df = temp_df.astype(float, errors="ignore")
    return temp_df


def air_quality_rank(date: str = "") -> pd.DataFrame:
    """
    真气网-168 城市 AQI 排行榜
    https://www.zq12369.com/environment.php?date=2020-03-12&tab=rank&order=DESC&type=DAY#rank
    :param date: "": 当前时刻空气质量排名; "20200312": 当日空气质量排名; "202003": 当月空气质量排名; "2019": 当年空气质量排名;
    :type date: str
    :return: 指定 date 类型的空气质量排名数据
    :rtype: pandas.DataFrame
    """
    if len(date) == 4:
        date = date
    elif len(date) == 6:
        date = "-".join([date[:4], date[4:6]])
    elif date == "":
        date = "实时"
    else:
        date = "-".join([date[:4], date[4:6], date[6:]])

    url = "https://www.zq12369.com/environment.php"

    if len(date.split("-")) == 3:
        params = {
            "date": date,
            "tab": "rank",
            "order": "DESC",
            "type": "DAY",
        }
        r = requests.get(url, params=params)
        return pd.read_html(StringIO(r.text))[1].iloc[1:, :]
    elif len(date.split("-")) == 2:
        params = {
            "month": date,
            "tab": "rank",
            "order": "DESC",
            "type": "MONTH",
        }
        r = requests.get(url, params=params)
        return pd.read_html(StringIO(r.text))[2].iloc[1:, :]
    elif len(date.split("-")) == 1 and date != "实时":
        params = {
            "year": date,
            "tab": "rank",
            "order": "DESC",
            "type": "YEAR",
        }
        r = requests.get(url, params=params)
        return pd.read_html(StringIO(r.text))[3].iloc[1:, :]
    if date == "实时":
        params = {
            "tab": "rank",
            "order": "DESC",
            "type": "MONTH",
        }
        r = requests.get(url, params=params)
        return pd.read_html(StringIO(r.text))[0].iloc[1:, :]


if __name__ == "__main__":
    air_city_table_df = air_city_table()
    print(air_city_table_df)

    air_quality_watch_point_df = air_quality_watch_point(
        city="杭州", start_date="20220408", end_date="20220409"
    )
    print(air_quality_watch_point_df)

    air_quality_hist_df = air_quality_hist(
        city="北京",
        period="day",
        start_date="20220801",
        end_date="20240402",
    )
    print(air_quality_hist_df)

    air_quality_rank_df = air_quality_rank()
    print(air_quality_rank_df)
