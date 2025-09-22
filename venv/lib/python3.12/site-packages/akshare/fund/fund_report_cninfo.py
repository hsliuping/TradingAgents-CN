# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/7/24 23:30
Desc: 巨潮资讯-数据中心-专题统计-基金报表
https://webapi.cninfo.com.cn/#/thematicStatistics
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


def fund_report_stock_cninfo(date: str = "20210630") -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-基金报表-基金重仓股
    https://webapi.cninfo.com.cn/#/thematicStatistics
    :param date: 报告时间; choice of {"XXXX0331", "XXXX0630", "XXXX0930", "XXXX1231"}
    :type date: str
    :return: 基金重仓股
    :rtype: pandas.DataFrame
    """
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1112"
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
        "rdate": "-".join([date[:4], date[4:6], date[6:]]),
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.rename(
        columns={
            "F003N": "持股总市值",
            "F002N": "持股总数",
            "F001N": "基金覆盖家数",
            "SECNAME": "股票简称",
            "ID": "序号",
            "SECCODE": "股票代码",
            "ENDDATE": "报告期",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "报告期",
            "基金覆盖家数",
            "持股总数",
            "持股总市值",
        ]
    ]
    temp_df["报告期"] = pd.to_datetime(temp_df["报告期"], errors="coerce").dt.date
    temp_df["持股总数"] = pd.to_numeric(temp_df["持股总数"], errors="coerce")
    temp_df["持股总市值"] = pd.to_numeric(temp_df["持股总市值"], errors="coerce")
    temp_df["基金覆盖家数"] = pd.to_numeric(temp_df["基金覆盖家数"], errors="coerce")
    temp_df["序号"] = range(1, len(temp_df) + 1)
    return temp_df


def fund_report_industry_allocation_cninfo(date: str = "20210630") -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-基金报表-基金行业配置
    https://webapi.cninfo.com.cn/#/thematicStatistics
    :param date: 报告时间; choice of {"XXXX0331", "XXXX0630", "XXXX0930", "XXXX1231"}, 从 2017 年开始
    :type date: str
    :return: 基金行业配置
    :rtype: pandas.DataFrame
    """
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1113"
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
        "rdate": "-".join([date[:4], date[4:6], date[6:]]),
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.rename(
        columns={
            "F004N": "行业规模",
            "F003N": "基金覆盖家数",
            "F002V": "证监会行业名称",
            "F001V": "行业编码",
            "ENDDATE": "报告期",
            "F005N": "占净资产比例",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "行业编码",
            "证监会行业名称",
            "报告期",
            "基金覆盖家数",
            "行业规模",
            "占净资产比例",
        ]
    ]
    temp_df["报告期"] = pd.to_datetime(temp_df["报告期"], errors="coerce").dt.date
    temp_df["基金覆盖家数"] = pd.to_numeric(temp_df["基金覆盖家数"], errors="coerce")
    temp_df["行业规模"] = pd.to_numeric(temp_df["行业规模"], errors="coerce")
    temp_df["占净资产比例"] = pd.to_numeric(temp_df["占净资产比例"], errors="coerce")
    return temp_df


def fund_report_asset_allocation_cninfo() -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-基金报表-基金资产配置
    https://webapi.cninfo.com.cn/#/thematicStatistics
    :return: 基金资产配置
    :rtype: pandas.DataFrame
    """
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1114"
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
    temp_df.rename(
        columns={
            "F001N": "基金覆盖家数",
            "F008N": "现金货币类占净资产比例",
            "F007N": "债券固定收益类占净资产比例",
            "F006N": "股票权益类占净资产比例",
            "ENDDATE": "报告期",
            "F005N": "基金市场净资产规模",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "报告期",
            "基金覆盖家数",
            "股票权益类占净资产比例",
            "债券固定收益类占净资产比例",
            "现金货币类占净资产比例",
            "基金市场净资产规模",
        ]
    ]
    temp_df["报告期"] = pd.to_datetime(temp_df["报告期"], errors="coerce").dt.date
    temp_df["基金覆盖家数"] = pd.to_numeric(temp_df["基金覆盖家数"], errors="coerce")
    temp_df["股票权益类占净资产比例"] = pd.to_numeric(
        temp_df["股票权益类占净资产比例"], errors="coerce"
    )
    temp_df["债券固定收益类占净资产比例"] = pd.to_numeric(
        temp_df["债券固定收益类占净资产比例"], errors="coerce"
    )
    temp_df["现金货币类占净资产比例"] = pd.to_numeric(
        temp_df["现金货币类占净资产比例"], errors="coerce"
    )
    temp_df["基金市场净资产规模"] = pd.to_numeric(
        temp_df["基金市场净资产规模"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    fund_report_stock_cninfo_df = fund_report_stock_cninfo(date="20210630")
    print(fund_report_stock_cninfo_df)

    fund_report_industry_allocation_cninfo_df = fund_report_industry_allocation_cninfo(
        date="20210930"
    )
    print(fund_report_industry_allocation_cninfo_df)

    fund_report_asset_allocation_cninfo_df = fund_report_asset_allocation_cninfo()
    print(fund_report_asset_allocation_cninfo_df)
