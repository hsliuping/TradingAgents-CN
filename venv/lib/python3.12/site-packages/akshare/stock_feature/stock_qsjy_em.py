#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/9/21 16:49
Desc: 东方财富网-数据中心-特色数据-券商业绩月报
http://data.eastmoney.com/other/qsjy.html
"""

import pandas as pd
import requests


def stock_qsjy_em(date: str = "20200731") -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-券商业绩月报
    http://data.eastmoney.com/other/qsjy.html
    :param date: 数据月份，从 2010-06-01 开始, e.g., 需要 2011 年 7 月, 则输入 2011-07-01
    :type date: str
    :return: 券商业绩月报
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "END_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_PERFORMANCE",
        "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,END_DATE,NETPROFIT,NP_YOY,NP_QOQ,ACCUMPROFIT,ACCUMPROFIT_YOY,OPERATE_INCOME,OI_YOY,OI_QOQ,ACCUMOI,ACCUMOI_YOY,NET_ASSETS,NA_YOY",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(END_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "代码",
        "简称",
        "-",
        "当月净利润-净利润",
        "当月净利润-同比增长",
        "当月净利润-环比增长",
        "当年累计净利润-累计净利润",
        "当年累计净利润-同比增长",
        "当月营业收入-营业收入",
        "当月营业收入-环比增长",
        "当月营业收入-同比增长",
        "当年累计营业收入-累计营业收入",
        "当年累计营业收入-同比增长",
        "净资产-净资产",
        "净资产-同比增长",
    ]
    temp_df = temp_df[
        [
            "简称",
            "代码",
            "当月净利润-净利润",
            "当月净利润-同比增长",
            "当月净利润-环比增长",
            "当年累计净利润-累计净利润",
            "当年累计净利润-同比增长",
            "当月营业收入-营业收入",
            "当月营业收入-环比增长",
            "当月营业收入-同比增长",
            "当年累计营业收入-累计营业收入",
            "当年累计营业收入-同比增长",
            "净资产-净资产",
            "净资产-同比增长",
        ]
    ]
    temp_df["当月净利润-净利润"] = pd.to_numeric(temp_df["当月净利润-净利润"])
    temp_df["当月净利润-同比增长"] = pd.to_numeric(temp_df["当月净利润-同比增长"])
    temp_df["当月净利润-环比增长"] = pd.to_numeric(temp_df["当月净利润-环比增长"])
    temp_df["当年累计净利润-累计净利润"] = pd.to_numeric(
        temp_df["当年累计净利润-累计净利润"]
    )
    temp_df["当年累计净利润-同比增长"] = pd.to_numeric(
        temp_df["当年累计净利润-同比增长"]
    )
    temp_df["当月营业收入-营业收入"] = pd.to_numeric(temp_df["当月营业收入-营业收入"])
    temp_df["当月营业收入-环比增长"] = pd.to_numeric(temp_df["当月营业收入-环比增长"])
    temp_df["当月营业收入-同比增长"] = pd.to_numeric(temp_df["当月营业收入-同比增长"])
    temp_df["当年累计营业收入-累计营业收入"] = pd.to_numeric(
        temp_df["当年累计营业收入-累计营业收入"]
    )
    temp_df["当年累计营业收入-同比增长"] = pd.to_numeric(
        temp_df["当年累计营业收入-同比增长"]
    )
    temp_df["净资产-净资产"] = pd.to_numeric(temp_df["净资产-净资产"])
    temp_df["净资产-同比增长"] = pd.to_numeric(temp_df["净资产-同比增长"])
    return temp_df


if __name__ == "__main__":
    stock_qsjy_em_df = stock_qsjy_em(date="20200430")
    print(stock_qsjy_em_df)
