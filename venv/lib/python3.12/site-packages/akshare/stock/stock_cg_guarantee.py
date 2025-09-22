#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/19 18:34
Desc: 巨潮资讯-数据中心-专题统计-公司治理-对外担保
https://webapi.cninfo.com.cn/#/thematicStatistics
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
    with open(setting_file_path, encoding="utf-8") as f:
        file_data = f.read()
    return file_data


def stock_cg_guarantee_cninfo(
    symbol: str = "全部", start_date: str = "20180630", end_date: str = "20210927"
) -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-公司治理-对外担保
    https://webapi.cninfo.com.cn/#/thematicStatistics
    :param symbol: choice of {"全部", "深市主板", "沪市", "创业板", "科创板"}
    :type symbol: str
    :param start_date: 开始统计时间
    :type start_date: str
    :param end_date: 结束统计时间
    :type end_date: str
    :return: 对外担保
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "全部": "",
        "深市主板": "012002",
        "沪市": "012001",
        "创业板": "012015",
        "科创板": "012029",
    }
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1054"
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "sdate": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "edate": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
        "market": symbol_map[symbol],
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "公告统计区间",
        "担保金融占净资产比例",
        "担保金额",
        "担保笔数",
        "证券简称",
        "证券代码",
        "归属于母公司所有者权益",
    ]
    temp_df = temp_df[
        [
            "证券代码",
            "证券简称",
            "公告统计区间",
            "担保笔数",
            "担保金额",
            "归属于母公司所有者权益",
            "担保金融占净资产比例",
        ]
    ]
    temp_df["担保笔数"] = pd.to_numeric(temp_df["担保笔数"], errors="coerce")
    temp_df["担保金额"] = pd.to_numeric(temp_df["担保金额"], errors="coerce")
    temp_df["归属于母公司所有者权益"] = pd.to_numeric(
        temp_df["归属于母公司所有者权益"], errors="coerce"
    )
    temp_df["担保金融占净资产比例"] = pd.to_numeric(
        temp_df["担保金融占净资产比例"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    stock_corporate_governance_guarantee_df = stock_cg_guarantee_cninfo(
        symbol="全部", start_date="20180928", end_date="20210927"
    )
    print(stock_corporate_governance_guarantee_df)
