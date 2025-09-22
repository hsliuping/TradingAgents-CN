# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/8/14 11:30
Desc: 同花顺-数据中心-可转债
https://data.10jqka.com.cn/ipo/bond/
"""

import pandas as pd
import requests


def bond_zh_cov_info_ths() -> pd.DataFrame:
    """
    同花顺-数据中心-可转债
    https://data.10jqka.com.cn/ipo/bond/
    :return: 可转债行情
    :rtype: pandas.DataFrame
    """
    url = "https://data.10jqka.com.cn/ipo/kzz/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/89.0.4389.90 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["list"])
    temp_df.rename(
        columns={
            "sub_date": "申购日期",
            "bond_code": "债券代码",
            "bond_name": "债券简称",
            "code": "正股代码",
            "name": "正股简称",
            "sub_code": "申购代码",
            "share_code": "原股东配售码",
            "sign_date": "中签公布日",
            "plan_total": "计划发行量",
            "issue_total": "实际发行量",
            "issue_price": "-",
            "success_rate": "中签率",
            "listing_date": "上市日期",
            "expire_date": "到期时间",
            "price": "转股价格",
            "quota": "每股获配额",
            "number": "中签号",
            "market_id": "-",
            "stock_market_id": "-",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "债券代码",
            "债券简称",
            "申购日期",
            "申购代码",
            "原股东配售码",
            "每股获配额",
            "计划发行量",
            "实际发行量",
            "中签公布日",
            "中签号",
            "上市日期",
            "正股代码",
            "正股简称",
            "转股价格",
            "到期时间",
            "中签率",
        ]
    ]
    temp_df["申购日期"] = pd.to_datetime(
        temp_df["申购日期"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df["中签公布日"] = pd.to_datetime(
        temp_df["中签公布日"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df["上市日期"] = pd.to_datetime(
        temp_df["上市日期"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df["到期时间"] = pd.to_datetime(
        temp_df["到期时间"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df["每股获配额"] = pd.to_numeric(temp_df["每股获配额"], errors="coerce")
    temp_df["计划发行量"] = pd.to_numeric(temp_df["计划发行量"], errors="coerce")
    temp_df["实际发行量"] = pd.to_numeric(temp_df["实际发行量"], errors="coerce")
    temp_df["转股价格"] = pd.to_numeric(temp_df["转股价格"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    bond_zh_cov_info_ths_df = bond_zh_cov_info_ths()
    print(bond_zh_cov_info_ths_df)
