#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/8/31 23:00
Desc: 金十数据-比特币持仓报告
https://datacenter.jin10.com/dc_report?name=bitcoint
"""

import pandas as pd
import requests


def crypto_bitcoin_hold_report():
    """
    金十数据-比特币持仓报告
    https://datacenter.jin10.com/dc_report?name=bitcoint
    :return: 比特币持仓报告
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-api.jin10.com/bitcoin_treasuries/list"
    headers = {
        "X-App-Id": "lnFP5lxse24wPgtY",
        "X-Version": "1.0.0",
    }
    r = requests.get(url, headers=headers)

    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["values"])
    temp_df.columns = [
        "代码",
        "公司名称-英文",
        "国家/地区",
        "市值",
        "比特币占市值比重",
        "持仓成本",
        "持仓占比",
        "持仓量",
        "当日持仓市值",
        "查询日期",
        "公告链接",
        "_",
        "分类",
        "倍数",
        "_",
        "公司名称-中文",
    ]
    temp_df = temp_df[
        [
            "代码",
            "公司名称-英文",
            "公司名称-中文",
            "国家/地区",
            "市值",
            "比特币占市值比重",
            "持仓成本",
            "持仓占比",
            "持仓量",
            "当日持仓市值",
            "查询日期",
            "公告链接",
            "分类",
            "倍数",
        ]
    ]
    temp_df["市值"] = pd.to_numeric(temp_df["市值"], errors="coerce")
    temp_df["比特币占市值比重"] = pd.to_numeric(
        temp_df["比特币占市值比重"], errors="coerce"
    )
    temp_df["持仓成本"] = pd.to_numeric(temp_df["持仓成本"], errors="coerce")
    temp_df["持仓占比"] = pd.to_numeric(temp_df["持仓占比"], errors="coerce")
    temp_df["持仓量"] = pd.to_numeric(temp_df["持仓量"], errors="coerce")
    temp_df["当日持仓市值"] = pd.to_numeric(temp_df["当日持仓市值"], errors="coerce")
    temp_df["倍数"] = pd.to_numeric(temp_df["倍数"], errors="coerce")
    temp_df["查询日期"] = pd.to_datetime(temp_df["查询日期"], errors="coerce").dt.date
    return temp_df


if __name__ == "__main__":
    crypto_bitcoin_hold_report_df = crypto_bitcoin_hold_report()
    print(crypto_bitcoin_hold_report_df)
