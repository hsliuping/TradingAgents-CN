#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/3/5 12:55
Desc: 上登债券信息网-债券成交概览
http://bond.sse.com.cn/data/statistics/overview/turnover/
"""

from io import BytesIO

import pandas as pd
import requests


def bond_cash_summary_sse(date: str = "20210111") -> pd.DataFrame:
    """
    上登债券信息网-市场数据-市场统计-市场概览-债券现券市场概览
    http://bond.sse.com.cn/data/statistics/overview/bondow/
    :param date: 指定日期
    :type date: str
    :return: 债券成交概览
    :rtype: pandas.DataFrame
    """
    url = "http://query.sse.com.cn/commonExcelDd.do"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Referer": "http://bond.sse.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
    }
    params = {
        "sqlId": "COMMON_SSEBOND_SCSJ_SCTJ_SCGL_ZQXQSCGL_CX_L",
        "TRADE_DATE": f"{date[:4]}-{date[4:6]}-{date[6:]}",
    }
    r = requests.get(url, params=params, headers=headers)
    temp_df = pd.read_excel(BytesIO(r.content), engine="xlrd")
    temp_df.columns = [
        "债券现货",
        "托管只数",
        "托管市值",
        "托管面值",
        "数据日期",
    ]
    temp_df["托管只数"] = pd.to_numeric(temp_df["托管只数"])
    temp_df["托管市值"] = pd.to_numeric(temp_df["托管市值"])
    temp_df["托管面值"] = pd.to_numeric(temp_df["托管面值"])
    temp_df["数据日期"] = pd.to_datetime(temp_df["数据日期"]).dt.date
    return temp_df


def bond_deal_summary_sse(date: str = "20210104") -> pd.DataFrame:
    """
    上登债券信息网-市场数据-市场统计-市场概览-债券成交概览
    http://bond.sse.com.cn/data/statistics/overview/turnover/
    :param date: 指定日期
    :type date: str
    :return: 债券成交概览
    :rtype: pandas.DataFrame
    """
    url = "http://query.sse.com.cn/commonExcelDd.do"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Referer": "http://bond.sse.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
    }
    params = {
        "sqlId": "COMMON_SSEBOND_SCSJ_SCTJ_SCGL_ZQCJGL_CX_L",
        "TRADE_DATE": f"{date[:4]}-{date[4:6]}-{date[6:]}",
    }
    r = requests.get(url, params=params, headers=headers)
    temp_df = pd.read_excel(BytesIO(r.content))
    temp_df.columns = [
        "债券类型",
        "当日成交笔数",
        "当日成交金额",
        "当年成交笔数",
        "当年成交金额",
        "数据日期",
    ]
    temp_df["当日成交笔数"] = pd.to_numeric(temp_df["当日成交笔数"])
    temp_df["当日成交金额"] = pd.to_numeric(temp_df["当日成交金额"])
    temp_df["当年成交笔数"] = pd.to_numeric(temp_df["当年成交笔数"])
    temp_df["当年成交金额"] = pd.to_numeric(temp_df["当年成交金额"])
    temp_df["数据日期"] = pd.to_datetime(temp_df["数据日期"]).dt.date
    return temp_df


if __name__ == "__main__":
    bond_cash_summary_sse_df = bond_cash_summary_sse(date="20210111")
    print(bond_cash_summary_sse_df)

    bond_summary_sse_df = bond_deal_summary_sse(date="20210111")
    print(bond_summary_sse_df)
