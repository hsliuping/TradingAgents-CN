#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/6/18 18:30
Desc: 巨潮资讯-数据中心-行业分析-行业市盈率
http://webapi.cninfo.com.cn/#/thematicStatistics?name=%E6%8A%95%E8%B5%84%E8%AF%84%E7%BA%A7
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


def stock_industry_pe_ratio_cninfo(
    symbol: str = "证监会行业分类", date: str = "20210910"
) -> pd.DataFrame:
    """
    巨潮资讯-数据中心-行业分析-行业市盈率
    http://webapi.cninfo.com.cn/#/thematicStatistics
    :param symbol: choice of {"证监会行业分类", "国证行业分类"}
    :type symbol: str
    :param date: 查询日期
    :type date: str
    :return: 行业市盈率
    :rtype: pandas.DataFrame
    """
    sort_code_map = {"证监会行业分类": "008001", "国证行业分类": "008200"}
    url = "http://webapi.cninfo.com.cn/api/sysapi/p_sysapi1087"
    params = {
        "tdate": "-".join([date[:4], date[4:6], date[6:]]),
        "sortcode": sort_code_map[symbol],
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
        "行业层级",
        "静态市盈率-算术平均",
        "静态市盈率-中位数",
        "静态市盈率-加权平均",
        "净利润-静态",
        "行业名称",
        "行业编码",
        "行业分类",
        "总市值-静态",
        "纳入计算公司数量",
        "变动日期",
        "公司数量",
    ]
    temp_df = temp_df[
        [
            "变动日期",
            "行业分类",
            "行业层级",
            "行业编码",
            "行业名称",
            "公司数量",
            "纳入计算公司数量",
            "总市值-静态",
            "净利润-静态",
            "静态市盈率-加权平均",
            "静态市盈率-中位数",
            "静态市盈率-算术平均",
        ]
    ]
    temp_df["行业层级"] = pd.to_numeric(temp_df["行业层级"], errors="coerce")
    temp_df["公司数量"] = pd.to_numeric(temp_df["公司数量"], errors="coerce")
    temp_df["纳入计算公司数量"] = pd.to_numeric(
        temp_df["纳入计算公司数量"], errors="coerce"
    )
    temp_df["总市值-静态"] = pd.to_numeric(temp_df["总市值-静态"], errors="coerce")
    temp_df["净利润-静态"] = pd.to_numeric(temp_df["净利润-静态"], errors="coerce")
    temp_df["静态市盈率-加权平均"] = pd.to_numeric(
        temp_df["静态市盈率-加权平均"], errors="coerce"
    )
    temp_df["静态市盈率-中位数"] = pd.to_numeric(
        temp_df["静态市盈率-中位数"], errors="coerce"
    )
    temp_df["静态市盈率-算术平均"] = pd.to_numeric(
        temp_df["静态市盈率-算术平均"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    stock_industry_pe_ratio_cninfo_df = stock_industry_pe_ratio_cninfo(
        symbol="国证行业分类", date="20240617"
    )
    print(stock_industry_pe_ratio_cninfo_df)
