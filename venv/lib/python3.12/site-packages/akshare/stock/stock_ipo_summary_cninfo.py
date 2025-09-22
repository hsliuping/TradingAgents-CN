#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/25 15:00
Desc: 巨潮资讯-个股-上市相关
https://webapi.cninfo.com.cn/#/company
"""

import pandas as pd
import requests
import py_mini_racer

from akshare.datasets import get_ths_js


def _get_file_content_ths(file: str = "cninfo.js") -> str:
    """
    获取 JS 文件的内容
    :param file:  JS 文件名
    :type file: str
    :return: 文件内容
    :rtype: str
    """
    setting_file_path = get_ths_js(file)
    with open(setting_file_path, encoding="utf8") as f:
        file_data = f.read()
    return file_data


def stock_ipo_summary_cninfo(symbol: str = "600030") -> pd.DataFrame:
    """
    巨潮资讯-个股-上市相关
    https://webapi.cninfo.com.cn/#/company
    :param symbol: 股票代码
    :type symbol: str
    :return: 上市相关
    :rtype: pandas.DataFrame
    """
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1134"
    params = {
        "scode": symbol,
    }
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("cninfo.js")
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
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.post(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame.from_dict(data_json["records"][0], orient="index").T
    temp_df.columns = [
        "股票代码",
        "招股公告日期",
        "中签率公告日",
        "每股面值",
        "总发行数量",
        "发行前每股净资产",
        "摊薄发行市盈率",
        "募集资金净额",
        "上网发行日期",
        "上市日期",
        "发行价格",
        "发行费用总额",
        "发行后每股净资产",
        "上网发行中签率",
        "主承销商",
    ]
    temp_df["招股公告日期"] = pd.to_datetime(
        temp_df["招股公告日期"], errors="coerce"
    ).dt.date
    temp_df["中签率公告日"] = pd.to_datetime(
        temp_df["中签率公告日"], errors="coerce"
    ).dt.date
    temp_df["上网发行日期"] = pd.to_datetime(
        temp_df["上网发行日期"], errors="coerce"
    ).dt.date
    temp_df["上市日期"] = pd.to_datetime(temp_df["上市日期"], errors="coerce").dt.date
    temp_df["每股面值"] = pd.to_numeric(temp_df["每股面值"], errors="coerce")
    temp_df["总发行数量"] = pd.to_numeric(temp_df["总发行数量"], errors="coerce")
    temp_df["发行前每股净资产"] = pd.to_numeric(
        temp_df["发行前每股净资产"], errors="coerce"
    )
    temp_df["摊薄发行市盈率"] = pd.to_numeric(
        temp_df["摊薄发行市盈率"], errors="coerce"
    )
    temp_df["募集资金净额"] = pd.to_numeric(temp_df["募集资金净额"], errors="coerce")
    temp_df["发行价格"] = pd.to_numeric(temp_df["发行价格"], errors="coerce")
    temp_df["发行费用总额"] = pd.to_numeric(temp_df["发行费用总额"], errors="coerce")
    temp_df["发行后每股净资产"] = pd.to_numeric(
        temp_df["发行后每股净资产"], errors="coerce"
    )
    temp_df["上网发行中签率"] = pd.to_numeric(
        temp_df["上网发行中签率"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    stock_ipo_summary_cninfo_df = stock_ipo_summary_cninfo(symbol="600030")
    print(stock_ipo_summary_cninfo_df)
