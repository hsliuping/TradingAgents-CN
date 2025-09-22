#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2021/11/16 20:40
Desc: 艺恩-艺人
艺人商业价值
艺人流量价值
https://www.endata.com.cn/Marketing/Artist/business.html
"""

import datetime
import json
import os

import pandas as pd  # type: ignore
import requests
import py_mini_racer  # type: ignore


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


def decrypt(origin_data: str = "") -> str:
    """
    解密艺恩的加密数据
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


def business_value_artist() -> pd.DataFrame:
    """
    艺恩-艺人-艺人商业价值
    https://www.endata.com.cn/Marketing/Artist/business.html
    :return: 艺人商业价值
    :rtype: pandas.DataFrame
    """
    url = "https://www.endata.com.cn/API/GetData.ashx"
    payload = {
        "Order": "BusinessValueIndex_L1",
        "OrderType": "DESC",
        "PageIndex": "1",
        "PageSize": "100",
        "MethodName": "Data_GetList_Star",
    }
    r = requests.post(url, data=payload)
    r.encoding = "utf8"
    data_json = json.loads(decrypt(r.text))
    temp_df = pd.DataFrame(data_json["Data"]["Table"])
    temp_df.columns = [
        "排名",
        "-",
        "艺人",
        "商业价值",
        "-",
        "专业热度",
        "关注热度",
        "预测热度",
        "美誉度",
        "-",
    ]
    temp_df = temp_df[
        ["排名", "艺人", "商业价值", "专业热度", "关注热度", "预测热度", "美誉度"]
    ]
    temp_df["统计日期"] = datetime.datetime.now().date().isoformat()
    return temp_df


def online_value_artist() -> pd.DataFrame:
    """
    艺恩-艺人-艺人流量价值
    https://www.endata.com.cn/Marketing/Artist/business.html
    :return: 艺人流量价值
    :rtype: pandas.DataFrame
    """
    url = "https://www.endata.com.cn/API/GetData.ashx"
    payload = {
        "Order": "FlowValueIndex_L1",
        "OrderType": "DESC",
        "PageIndex": 1,
        "PageSize": 100,
        "MethodName": "Data_GetList_Star",
    }
    r = requests.post(url, data=payload)
    r.encoding = "utf8"
    data_json = json.loads(decrypt(r.text))
    temp_df = pd.DataFrame(data_json["Data"]["Table"])
    temp_df.columns = [
        "排名",
        "-",
        "艺人",
        "-",
        "流量价值",
        "专业热度",
        "关注热度",
        "预测热度",
        "-",
        "带货力",
    ]
    temp_df = temp_df[
        ["排名", "艺人", "流量价值", "专业热度", "关注热度", "预测热度", "带货力"]
    ]
    temp_df["统计日期"] = datetime.datetime.now().date().isoformat()
    return temp_df


if __name__ == "__main__":
    business_value_artist_df = business_value_artist()
    print(business_value_artist_df)

    online_value_artist_df = online_value_artist()
    print(online_value_artist_df)
