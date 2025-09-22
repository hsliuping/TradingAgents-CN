#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/7/24 23:30
Desc: 巨潮资讯-数据中心-专题统计-公司治理-股权质押
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


def stock_cg_equity_mortgage_cninfo(date: str = "20210930") -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-公司治理-股权质押
    https://webapi.cninfo.com.cn/#/thematicStatistics
    :param date: 开始统计时间
    :type date: str
    :return: 股权质押
    :rtype: pandas.DataFrame
    """
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1094"
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
        "tdate": "-".join([date[:4], date[4:6], date[6:]]),
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "质押解除数量",
        "股票简称",
        "公告日期",
        "质押事项",
        "质权人",
        "出质人",
        "股票代码",
        "占总股本比例",
        "累计质押占总股本比例",
        "质押数量",
    ]
    temp_df = temp_df[
        [
            "股票代码",
            "股票简称",
            "公告日期",
            "出质人",
            "质权人",
            "质押数量",
            "占总股本比例",
            "质押解除数量",
            "质押事项",
            "累计质押占总股本比例",
        ]
    ]
    temp_df["公告日期"] = pd.to_datetime(temp_df["公告日期"], errors="coerce").dt.date
    temp_df["质押数量"] = pd.to_numeric(temp_df["质押数量"], errors="coerce")
    temp_df["占总股本比例"] = pd.to_numeric(temp_df["占总股本比例"], errors="coerce")
    temp_df["质押解除数量"] = pd.to_numeric(temp_df["质押解除数量"], errors="coerce")
    temp_df["累计质押占总股本比例"] = pd.to_numeric(
        temp_df["累计质押占总股本比例"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    stock_cg_equity_mortgage_cninfo_df = stock_cg_equity_mortgage_cninfo(
        date="20210930"
    )
    print(stock_cg_equity_mortgage_cninfo_df)
