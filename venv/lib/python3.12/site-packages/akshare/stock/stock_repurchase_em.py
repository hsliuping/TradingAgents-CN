# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2022/8/29 14:20
Desc: 东方财富网-数据中心-股票回购-股票回购数据
https://data.eastmoney.com/gphg/hglist.html
"""

import pandas as pd
import requests
from tqdm import tqdm


def stock_repurchase_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-股票回购-股票回购数据
    https://data.eastmoney.com/gphg/hglist.html
    :return: 股票回购数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "UPD,DIM_DATE,DIM_SCODE",
        "sortTypes": "-1,-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPTA_WEB_GETHGLIST_NEW",
        "columns": "ALL",
        "source": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.rename(
        {
            "DIM_SCODE": "股票代码",
            "SECURITYSHORTNAME": "股票简称",
            "NEWPRICE": "最新价",
            "REPURPRICECAP": "计划回购价格区间",
            "REPURNUMLOWER": "计划回购数量区间-下限",
            "REPURNUMCAP": "计划回购数量区间-上限",
            "ZSZXX": "占公告前一日总股本比例-下限",
            "ZSZSX": "占公告前一日总股本比例-上限",
            "JEXX": "计划回购金额区间-下限",
            "JESX": "计划回购金额区间-上限",
            "DIM_TRADEDATE": "回购起始时间",
            "REPURPROGRESS": "实施进度",
            "REPURPRICELOWER1": "已回购股份价格区间-下限",
            "REPURPRICECAP1": "已回购股份价格区间-上限",
            "REPURNUM": "已回购股份数量",
            "REPURAMOUNT": "已回购金额",
            "UPDATEDATE": "最新公告日期",
        },
        axis="columns",
        inplace=True,
    )
    big_df = big_df[
        [
            "股票代码",
            "股票简称",
            "最新价",
            "计划回购价格区间",
            "计划回购数量区间-下限",
            "计划回购数量区间-上限",
            "占公告前一日总股本比例-下限",
            "占公告前一日总股本比例-上限",
            "计划回购金额区间-下限",
            "计划回购金额区间-上限",
            "回购起始时间",
            "实施进度",
            "已回购股份价格区间-下限",
            "已回购股份价格区间-上限",
            "已回购股份数量",
            "已回购金额",
            "最新公告日期",
        ]
    ]
    big_df.reset_index(inplace=True)
    big_df.rename(
        {
            "index": "序号",
        },
        axis="columns",
        inplace=True,
    )
    big_df["序号"] = big_df.index + 1
    process_map = {
        "001": "董事会预案",
        "002": "股东大会通过",
        "003": "股东大会否决",
        "004": "实施中",
        "005": "停止实施",
        "006": "完成实施",
    }
    big_df["实施进度"] = big_df["实施进度"].map(process_map)
    big_df["回购起始时间"] = pd.to_datetime(big_df["回购起始时间"]).dt.date
    big_df["最新公告日期"] = pd.to_datetime(big_df["最新公告日期"]).dt.date
    big_df["最新价"] = pd.to_numeric(big_df["最新价"])
    big_df["计划回购价格区间"] = pd.to_numeric(big_df["计划回购价格区间"])
    big_df["计划回购数量区间-下限"] = pd.to_numeric(big_df["计划回购数量区间-下限"])
    big_df["计划回购数量区间-上限"] = pd.to_numeric(big_df["计划回购数量区间-上限"])
    big_df["占公告前一日总股本比例-上限"] = pd.to_numeric(
        big_df["占公告前一日总股本比例-上限"]
    )
    big_df["占公告前一日总股本比例-下限"] = pd.to_numeric(
        big_df["占公告前一日总股本比例-下限"]
    )
    big_df["计划回购金额区间-上限"] = pd.to_numeric(big_df["计划回购金额区间-上限"])
    big_df["计划回购金额区间-下限"] = pd.to_numeric(big_df["计划回购金额区间-下限"])
    big_df["已回购股份价格区间-下限"] = pd.to_numeric(big_df["已回购股份价格区间-下限"])
    big_df["已回购股份价格区间-上限"] = pd.to_numeric(big_df["已回购股份价格区间-上限"])
    big_df["已回购股份数量"] = pd.to_numeric(big_df["已回购股份数量"])
    big_df["已回购金额"] = pd.to_numeric(big_df["已回购金额"])
    return big_df


if __name__ == "__main__":
    stock_repurchase_em_df = stock_repurchase_em()
    print(stock_repurchase_em_df)
