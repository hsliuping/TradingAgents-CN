#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/7/25 14:30
Desc: 巨潮资讯-数据中心-新股数据
https://webapi.cninfo.com.cn/#/xinguList
"""

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


def stock_new_gh_cninfo() -> pd.DataFrame:
    """
    巨潮资讯-数据中心-新股数据-新股过会
    https://webapi.cninfo.com.cn/#/xinguList
    :return: 新股过会
    :rtype: pandas.DataFrame
    """
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1098"
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
    r = requests.post(url, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "公司名称",
        "上会日期",
        "审核类型",
        "审议内容",
        "审核结果",
        "审核公告日",
    ]
    temp_df["上会日期"] = pd.to_datetime(temp_df["上会日期"], errors="coerce").dt.date
    temp_df["审核公告日"] = pd.to_datetime(
        temp_df["审核公告日"], errors="coerce"
    ).dt.date
    return temp_df


def stock_new_ipo_cninfo() -> pd.DataFrame:
    """
    巨潮资讯-数据中心-新股数据-新股发行
    https://webapi.cninfo.com.cn/#/xinguList
    :return: 新股发行
    :rtype: pandas.DataFrame
    """
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1097"
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
        "timetype": "36",
        "market": "ALL",
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "摇号结果公告日",
        "中签公告日",
        "证券简称",
        "上市日期",
        "中签缴款日",
        "申购日期",
        "发行价",
        "证劵代码",
        "上网发行中签率",
        "总发行数量",
        "发行市盈率",
        "上网发行数量",
        "网上申购上限",
    ]
    temp_df = temp_df[
        [
            "证劵代码",
            "证券简称",
            "上市日期",
            "申购日期",
            "发行价",
            "总发行数量",
            "发行市盈率",
            "上网发行中签率",
            "摇号结果公告日",
            "中签公告日",
            "中签缴款日",
            "网上申购上限",
            "上网发行数量",
        ]
    ]
    temp_df["摇号结果公告日"] = pd.to_datetime(
        temp_df["摇号结果公告日"], errors="coerce"
    ).dt.date
    temp_df["中签公告日"] = pd.to_datetime(
        temp_df["中签公告日"], errors="coerce"
    ).dt.date
    temp_df["上市日期"] = pd.to_datetime(temp_df["上市日期"], errors="coerce").dt.date
    temp_df["中签缴款日"] = pd.to_datetime(
        temp_df["中签缴款日"], errors="coerce"
    ).dt.date
    temp_df["申购日期"] = pd.to_datetime(temp_df["申购日期"], errors="coerce").dt.date
    temp_df["发行价"] = pd.to_numeric(temp_df["发行价"], errors="coerce")
    temp_df["上网发行中签率"] = pd.to_numeric(
        temp_df["上网发行中签率"], errors="coerce"
    )
    temp_df["总发行数量"] = pd.to_numeric(temp_df["总发行数量"], errors="coerce")
    temp_df["发行市盈率"] = pd.to_numeric(temp_df["发行市盈率"], errors="coerce")
    temp_df["上网发行数量"] = pd.to_numeric(temp_df["上网发行数量"], errors="coerce")
    temp_df["网上申购上限"] = pd.to_numeric(temp_df["网上申购上限"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_new_gh_cninfo_df = stock_new_gh_cninfo()
    print(stock_new_gh_cninfo_df)

    stock_new_ipo_cninfo_df = stock_new_ipo_cninfo()
    print(stock_new_ipo_cninfo_df)
