#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/7/24 23:30
Desc: 巨潮资讯-数据中心-专题统计-股东股本-股东人数及持股集中度
https://webapi.cninfo.com.cn/#/thematicStatistics
"""

import pandas as pd
import py_mini_racer
import requests

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
    with open(setting_file_path, encoding="utf-8") as f:
        file_data = f.read()
    return file_data


def stock_hold_num_cninfo(date: str = "20210630") -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-股东股本-股东人数及持股集中度
    https://webapi.cninfo.com.cn/#/thematicStatistics
    :param date: choice of {"XXXX0331", "XXXX0630", "XXXX0930", "XXXX1231"}; 从 20170331 开始
    :type date: str
    :return: 股东人数及持股集中度
    :rtype: pandas.DataFrame
    """
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1034"
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("cninfo.js")
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
        "rdate": date,
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "本期人均持股数量",
        "股东人数增幅",
        "上期股东人数",
        "本期股东人数",
        "证券简称",
        "证券代码",
        "人均持股数量增幅",
        "变动日期",
        "上期人均持股数量",
    ]
    temp_df = temp_df[
        [
            "证券代码",
            "证券简称",
            "变动日期",
            "本期股东人数",
            "上期股东人数",
            "股东人数增幅",
            "本期人均持股数量",
            "上期人均持股数量",
            "人均持股数量增幅",
        ]
    ]
    temp_df["变动日期"] = pd.to_datetime(temp_df["变动日期"], errors="coerce").dt.date
    temp_df["本期人均持股数量"] = pd.to_numeric(
        temp_df["本期人均持股数量"], errors="coerce"
    )
    temp_df["股东人数增幅"] = pd.to_numeric(temp_df["股东人数增幅"], errors="coerce")
    temp_df["上期股东人数"] = pd.to_numeric(temp_df["上期股东人数"], errors="coerce")
    temp_df["本期股东人数"] = pd.to_numeric(temp_df["本期股东人数"], errors="coerce")
    temp_df["人均持股数量增幅"] = pd.to_numeric(
        temp_df["人均持股数量增幅"], errors="coerce"
    )
    temp_df["上期人均持股数量"] = pd.to_numeric(
        temp_df["上期人均持股数量"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    stock_hold_num_cninfo_df = stock_hold_num_cninfo(date="20210630")
    print(stock_hold_num_cninfo_df)
