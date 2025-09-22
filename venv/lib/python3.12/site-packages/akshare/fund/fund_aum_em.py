#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/11/11 16:30
Desc: 东方财富-基金
"""

from io import StringIO

import pandas as pd
import requests


def fund_aum_em() -> pd.DataFrame:
    """
    东方财富-基金-基金公司排名列表
    https://fund.eastmoney.com/Company/lsgm.html
    :return: 基金公司排名列表
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/Company/home/gspmlist"
    params = {"fundType": "0"}
    r = requests.get(url, params=params)
    temp_df = pd.read_html(StringIO(r.text))[0]
    del temp_df["相关链接"]
    del temp_df["天相评级"]
    temp_df.columns = [
        "序号",
        "基金公司",
        "成立时间",
        "全部管理规模",
        "全部基金数",
        "全部经理数",
    ]
    expanded_df = temp_df["全部管理规模"].str.split(" ", expand=True)
    temp_df["全部管理规模"] = expanded_df.iloc[:, 0].str.replace(",", "")
    temp_df["更新日期"] = expanded_df.iloc[:, 1]
    temp_df["全部管理规模"] = pd.to_numeric(temp_df["全部管理规模"], errors="coerce")
    temp_df["全部基金数"] = pd.to_numeric(temp_df["全部基金数"], errors="coerce")
    temp_df["全部经理数"] = pd.to_numeric(temp_df["全部经理数"], errors="coerce")
    temp_df["成立时间"] = pd.to_datetime(temp_df["成立时间"], errors="coerce").dt.date
    return temp_df


def fund_aum_trend_em() -> pd.DataFrame:
    """
    东方财富-基金-基金市场管理规模走势图
    https://fund.eastmoney.com/Company/default.html
    :return: 基金市场管理规模走势图
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/Company/home/GetFundTotalScaleForChart"
    payload = {"fundType": "0"}
    r = requests.get(url, data=payload)
    data_json = r.json()
    temp_df = pd.DataFrame()
    temp_df["date"] = data_json["x"]
    temp_df["value"] = data_json["y"]
    temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
    return temp_df


def fund_aum_hist_em(year: str = "2023") -> pd.DataFrame:
    """
    东方财富-基金-基金公司历年管理规模排行列表
    https://fund.eastmoney.com/Company/lsgm.html
    :return: 基金公司历年管理规模排行列表
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/Company/home/HistoryScaleTable"
    params = {"year": year}
    r = requests.get(url, params=params)
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df.columns = [
        "序号",
        "基金公司",
        "总规模",
        "股票型",
        "混合型",
        "债券型",
        "指数型",
        "QDII",
        "货币型",
    ]
    temp_df["总规模"] = pd.to_numeric(temp_df["总规模"], errors="coerce")
    temp_df["股票型"] = pd.to_numeric(temp_df["股票型"], errors="coerce")
    temp_df["混合型"] = pd.to_numeric(temp_df["混合型"], errors="coerce")
    temp_df["债券型"] = pd.to_numeric(temp_df["债券型"], errors="coerce")
    temp_df["指数型"] = pd.to_numeric(temp_df["指数型"], errors="coerce")
    temp_df["QDII"] = pd.to_numeric(temp_df["QDII"], errors="coerce")
    temp_df["货币型"] = pd.to_numeric(temp_df["货币型"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    fund_aum_em_df = fund_aum_em()
    print(fund_aum_em_df)

    fund_aum_trend_em_df = fund_aum_trend_em()
    print(fund_aum_trend_em_df)

    fund_em_aum_hist_df = fund_aum_hist_em(year="2023")
    print(fund_em_aum_hist_df)
