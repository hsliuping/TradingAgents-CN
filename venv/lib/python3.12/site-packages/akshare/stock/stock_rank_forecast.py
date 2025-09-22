#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/8/28 15:30
Desc: 巨潮资讯-数据中心-评级预测-投资评级
https://webapi.cninfo.com.cn/#/thematicStatistics?name=%E6%8A%95%E8%B5%84%E8%AF%84%E7%BA%A7
"""

import pandas as pd
import requests
import py_mini_racer

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


def stock_rank_forecast_cninfo(date: str = "20230817") -> pd.DataFrame:
    """
    巨潮资讯-数据中心-评级预测-投资评级
    https://webapi.cninfo.com.cn/#/thematicStatistics?name=%E6%8A%95%E8%B5%84%E8%AF%84%E7%BA%A7
    :param date: 查询日期
    :type date: str
    :return: 投资评级
    :rtype: pandas.DataFrame
    """
    url = "http://webapi.cninfo.com.cn/api/sysapi/p_sysapi1089"
    params = {"tdate": "-".join([date[:4], date[4:6], date[6:]])}
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
        "Origin": "http://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.post(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "证券简称",
        "发布日期",
        "前一次投资评级",
        "评级变化",
        "目标价格-上限",
        "是否首次评级",
        "投资评级",
        "研究员名称",
        "研究机构简称",
        "目标价格-下限",
        "证券代码",
    ]
    temp_df = temp_df[
        [
            "证券代码",
            "证券简称",
            "发布日期",
            "研究机构简称",
            "研究员名称",
            "投资评级",
            "是否首次评级",
            "评级变化",
            "前一次投资评级",
            "目标价格-下限",
            "目标价格-上限",
        ]
    ]
    temp_df["目标价格-上限"] = pd.to_numeric(temp_df["目标价格-上限"], errors="coerce")
    temp_df["目标价格-下限"] = pd.to_numeric(temp_df["目标价格-下限"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_rank_forecast_cninfo_df = stock_rank_forecast_cninfo(date="20230817")
    print(stock_rank_forecast_cninfo_df)
