#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/3/25 22:15
Desc: 东方财富个股人气榜-港股市场
https://guba.eastmoney.com/rank/
"""

import pandas as pd
import requests


def stock_hk_hot_rank_em() -> pd.DataFrame:
    """
    东方财富-个股人气榜-人气榜-港股市场
    https://guba.eastmoney.com/rank/
    :return: 人气榜
    :rtype: pandas.DataFrame
    """
    url = "https://emappdata.eastmoney.com/stockrank/getAllCurrHkUsList"
    payload = {
        "appId": "appId01",
        "globalId": "786e4c21-70dc-435a-93bb-38",
        "marketType": "000003",
        "pageNo": 1,
        "pageSize": 100,
    }
    r = requests.post(url, json=payload)
    data_json = r.json()
    temp_rank_df = pd.DataFrame(data_json["data"])
    temp_rank_df["mark"] = ["116." + item[3:] for item in temp_rank_df["sc"]]
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
    temp_df["当前排名"] = temp_rank_df["rk"]
    temp_df["代码"] = temp_rank_df["sc"].str.split("|").str[1]
    temp_df = temp_df[
        [
            "当前排名",
            "代码",
            "股票名称",
            "最新价",
            "涨跌幅",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    return temp_df


def stock_hk_hot_rank_detail_em(symbol: str = "00700") -> pd.DataFrame:
    """
    东方财富-个股人气榜-历史趋势
    https://guba.eastmoney.com/rank/stock?code=HK_00700
    :param symbol: 带市场表示的证券代码
    :type symbol: str
    :return: 个股的历史趋势
    :rtype: pandas.DataFrame
    """
    url_rank = "https://emappdata.eastmoney.com/stockrank/getHisHkUsList"
    payload = {
        "appId": "appId01",
        "globalId": "786e4c21-70dc-435a-93bb-38",
        "marketType": "000003",
        "srcSecurityCode": f"HK|{symbol}",
    }
    r = requests.post(url_rank, json=payload)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["证券代码"] = symbol
    temp_df.columns = ["时间", "排名", "证券代码"]
    temp_df = temp_df[["时间", "排名", "证券代码"]]
    return temp_df


def stock_hk_hot_rank_detail_realtime_em(symbol: str = "00700") -> pd.DataFrame:
    """
    东方财富-个股人气榜-实时变动
    https://guba.eastmoney.com/rank/stock?code=HK_00700
    :param symbol: 带市场表示的证券代码
    :type symbol: str
    :return: 实时变动
    :rtype: pandas.DataFrame
    """
    url = "https://emappdata.eastmoney.com/stockrank/getCurrentHkUsList"
    payload = {
        "appId": "appId01",
        "globalId": "786e4c21-70dc-435a-93bb-38",
        "marketType": "000003",
        "srcSecurityCode": f"HK|{symbol}",
    }
    r = requests.post(url, json=payload)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["时间", "排名"]
    return temp_df


def stock_hk_hot_rank_latest_em(symbol: str = "00700") -> pd.DataFrame:
    """
    东方财富-个股人气榜-最新排名
    https://guba.eastmoney.com/rank/stock?code=HK_00700
    :param symbol: 带市场表示的证券代码
    :type symbol: str
    :return: 最新排名
    :rtype: pandas.DataFrame
    """
    url = "https://emappdata.eastmoney.com/stockrank/getCurrentHkUsLatest"
    payload = {
        "appId": "appId01",
        "globalId": "786e4c21-70dc-435a-93bb-38",
        "marketType": "000003",
        "srcSecurityCode": f"HK|{symbol}",
    }
    r = requests.post(url, json=payload)
    data_json = r.json()
    temp_df = pd.DataFrame.from_dict(data_json["data"], orient="index")
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["item", "value"]
    return temp_df


if __name__ == "__main__":
    stock_hk_hot_rank_em_df = stock_hk_hot_rank_em()
    print(stock_hk_hot_rank_em_df)

    stock_hk_hot_rank_detail_em_df = stock_hk_hot_rank_detail_em(symbol="00700")
    print(stock_hk_hot_rank_detail_em_df)

    stock_hk_hot_rank_detail_realtime_em_df = stock_hk_hot_rank_detail_realtime_em(
        symbol="00700"
    )
    print(stock_hk_hot_rank_detail_realtime_em_df)

    stock_hk_hot_rank_latest_em_df = stock_hk_hot_rank_latest_em(symbol="00700")
    print(stock_hk_hot_rank_latest_em_df)
