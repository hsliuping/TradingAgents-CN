#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/6/15 15:15
Desc: 东方财富个股人气榜
https://guba.eastmoney.com/rank/
"""

import pandas as pd
import requests


def stock_hot_up_em() -> pd.DataFrame:
    """
    东方财富-个股人气榜-飙升榜
    https://guba.eastmoney.com/rank/
    :return: 飙升榜
    :rtype: pandas.DataFrame
    """
    url = "https://emappdata.eastmoney.com/stockrank/getAllHisRcList"
    payload = {
        "appId": "appId01",
        "globalId": "786e4c21-70dc-435a-93bb-38",
        "marketType": "",
        "pageNo": 1,
        "pageSize": 100,
    }
    r = requests.post(url, json=payload)
    data_json = r.json()
    temp_rank_df = pd.DataFrame(data_json["data"])

    temp_rank_df["mark"] = [
        "0" + "." + item[2:] if "SZ" in item else "1" + "." + item[2:]
        for item in temp_rank_df["sc"]
    ]
    ",".join(temp_rank_df["mark"]) + "?v=08926209912590994"
    params = {
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "fltt": "2",
        "invt": "2",
        "fields": "f14,f3,f12,f2",
        "secids": ",".join(temp_rank_df["mark"]) + ",?v=08926209912590994",
    }
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["diff"])
    temp_df.columns = ["最新价", "涨跌幅", "代码", "股票名称"]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["涨跌额"] = temp_df["最新价"] * temp_df["涨跌幅"] / 100
    temp_df["当前排名"] = temp_rank_df["rk"]
    temp_df["代码"] = temp_rank_df["sc"]
    temp_df["排名较昨日变动"] = temp_rank_df["hrc"]
    temp_df = temp_df[
        [
            "排名较昨日变动",
            "当前排名",
            "代码",
            "股票名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
        ]
    ]
    temp_df["排名较昨日变动"] = pd.to_numeric(
        temp_df["排名较昨日变动"], errors="coerce"
    )
    temp_df["当前排名"] = pd.to_numeric(temp_df["当前排名"], errors="coerce")
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_hot_up_em_df = stock_hot_up_em()
    print(stock_hot_up_em_df)
