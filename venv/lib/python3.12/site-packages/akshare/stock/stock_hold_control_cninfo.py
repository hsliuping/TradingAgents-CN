#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/7/24 23:30
Desc: 巨潮资讯-数据中心-专题统计-股东股本-实际控制人持股变动
https://webapi.cninfo.com.cn/#/thematicStatistics

巨潮资讯-数据中心-专题统计-股东股本-高管持股变动明细
https://webapi.cninfo.com.cn/#/thematicStatistics
"""

import datetime

import pandas as pd
import py_mini_racer
import requests

from akshare.datasets import get_ths_js


def _get_file_content_cninfo(file: str = "cninfo.js") -> str:
    """
    获取 JS 文件的内容
    :param file:  JS 文件名
    :type file: str
    :return: 文件内容
    :rtype: str
    """
    setting_file_path = get_ths_js(file)
    with open(setting_file_path, encoding="utf-8") as f:
        file_data = f.read()
    return file_data


def stock_hold_control_cninfo(symbol: str = "全部") -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-股东股本-实际控制人持股变动
    https://webapi.cninfo.com.cn/#/thematicStatistics
    :param symbol: choice of {"单独控制", "实际控制人", "一致行动人", "家族控制", "全部"}; 从 2010 开始
    :type symbol: str
    :return: 实际控制人持股变动
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "单独控制": "069001",
        "实际控制人": "069002",
        "一致行动人": "069003",
        "家族控制": "069004",
        "全部": "",
    }
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1033"
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_cninfo("cninfo.js")
    js_code.eval(js_content)
    mcode = js_code.call("getResCode1")
    headers = {
        "Accept": "*/*",
        "Accept-Enckey": mcode,
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "Origin": "https://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "https://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "ctype": symbol_map[symbol],
    }
    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "控股比例",
        "控股数量",
        "证券简称",
        "实际控制人名称",
        "直接控制人名称",
        "控制类型",
        "证券代码",
        "变动日期",
    ]
    temp_df = temp_df[
        [
            "证券代码",
            "证券简称",
            "变动日期",
            "实际控制人名称",
            "控股数量",
            "控股比例",
            "直接控制人名称",
            "控制类型",
        ]
    ]
    temp_df["变动日期"] = pd.to_datetime(temp_df["变动日期"], errors="coerce").dt.date
    temp_df["控股数量"] = pd.to_numeric(temp_df["控股数量"], errors="coerce")
    temp_df["控股比例"] = pd.to_numeric(temp_df["控股比例"], errors="coerce")
    return temp_df


def stock_hold_management_detail_cninfo(symbol: str = "增持") -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-股东股本-高管持股变动明细
    https://webapi.cninfo.com.cn/#/thematicStatistics
    :param symbol: choice of {"增持", "减持"}
    :type symbol: str
    :return: 高管持股变动明细
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "增持": "B",
        "减持": "S",
    }
    current_date = datetime.datetime.now().date().isoformat()
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1030"
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_cninfo("cninfo.js")
    js_code.eval(js_content)
    mcode = js_code.call("getResCode1")
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "Accept-Enckey": mcode,
        "Origin": "https://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "https://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "sdate": str(int(current_date[:4]) - 1) + current_date[4:],
        "edate": current_date,
        "varytype": symbol_map[symbol],
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "证券简称",
        "公告日期",
        "高管姓名",
        "期末市值",
        "成交均价",
        "证券代码",
        "变动比例",
        "变动数量",
        "截止日期",
        "期末持股数量",
        "期初持股数量",
        "变动人与董监高关系",
        "董监高职务",
        "董监高姓名",
        "数据来源",
        "持股变动原因",
    ]
    temp_df = temp_df[
        [
            "证券代码",
            "证券简称",
            "截止日期",
            "公告日期",
            "高管姓名",
            "董监高姓名",
            "董监高职务",
            "变动人与董监高关系",
            "期初持股数量",
            "期末持股数量",
            "变动数量",
            "变动比例",
            "成交均价",
            "期末市值",
            "持股变动原因",
            "数据来源",
        ]
    ]
    temp_df["截止日期"] = pd.to_datetime(temp_df["截止日期"], errors="coerce").dt.date
    temp_df["公告日期"] = pd.to_datetime(temp_df["公告日期"], errors="coerce").dt.date
    temp_df["期初持股数量"] = pd.to_numeric(temp_df["期初持股数量"], errors="coerce")
    temp_df["期末持股数量"] = pd.to_numeric(temp_df["期末持股数量"], errors="coerce")
    temp_df["变动数量"] = pd.to_numeric(temp_df["变动数量"], errors="coerce")
    temp_df["变动比例"] = pd.to_numeric(temp_df["变动比例"], errors="coerce")
    temp_df["成交均价"] = pd.to_numeric(temp_df["成交均价"], errors="coerce")
    temp_df["期末市值"] = pd.to_numeric(temp_df["期末市值"], errors="coerce")
    return temp_df


def stock_hold_change_cninfo(symbol: str = "全部") -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-股东股本-股本变动
    https://webapi.cninfo.com.cn/#/thematicStatistics
    :param symbol: choice of {"深市主板", "沪市", "创业板", "科创板", "北交所", "全部"}
    :type symbol: str
    :return: 股本变动
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "深市主板": "012002",
        "沪市": "012001",
        "创业板": "012015",
        "科创板": "012029",
        "北交所": "012046",
        "全部": "",
    }
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1029"
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_cninfo("cninfo.js")
    js_code.eval(js_content)
    mcode = js_code.call("getResCode1")
    headers = {
        "Accept": "/",
        "Accept-Enckey": mcode,
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "Origin": "https://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "https://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "market": symbol_map[symbol],
    }
    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "已流通股份",
        "总股本",
        "交易市场",
        "证券简称",
        "公告日期",
        "变动原因",
        "证券代码",
        "变动日期",
        "流通受限股份",
        "已流通比例",
    ]
    temp_df = temp_df[
        [
            "证券代码",
            "证券简称",
            "交易市场",
            "公告日期",
            "变动日期",
            "变动原因",
            "总股本",
            "已流通股份",
            "已流通比例",
            "流通受限股份",
        ]
    ]
    temp_df["变动日期"] = pd.to_datetime(temp_df["变动日期"], errors="coerce").dt.date
    temp_df["公告日期"] = pd.to_datetime(temp_df["公告日期"], errors="coerce").dt.date
    temp_df["总股本"] = pd.to_numeric(temp_df["总股本"], errors="coerce")
    temp_df["已流通股份"] = pd.to_numeric(temp_df["已流通股份"], errors="coerce")
    temp_df["已流通比例"] = pd.to_numeric(temp_df["已流通比例"], errors="coerce")
    temp_df["流通受限股份"] = pd.to_numeric(temp_df["流通受限股份"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_hold_control_cninfo_df = stock_hold_control_cninfo(symbol="全部")
    print(stock_hold_control_cninfo_df)

    stock_hold_management_detail_cninfo_df = stock_hold_management_detail_cninfo(
        symbol="增持"
    )
    print(stock_hold_management_detail_cninfo_df)

    stock_hold_change_cninfo_df = stock_hold_change_cninfo(symbol="全部")
    print(stock_hold_change_cninfo_df)
