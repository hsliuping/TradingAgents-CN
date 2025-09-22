#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/7/8 17:15
Desc: 东方财富个股人气榜
https://guba.eastmoney.com/rank/
"""

import pandas as pd
import requests


def stock_hot_rank_em() -> pd.DataFrame:
    """
    东方财富-个股人气榜-人气榜
    https://guba.eastmoney.com/rank/
    :return: 人气榜
    :rtype: pandas.DataFrame
    """
    url = "https://emappdata.eastmoney.com/stockrank/getAllCurrentList"
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
    temp_df = temp_df[
        [
            "当前排名",
            "代码",
            "股票名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
        ]
    ]
    temp_df["当前排名"] = pd.to_numeric(temp_df["当前排名"], errors="coerce")
    return temp_df


def stock_hot_rank_detail_em(symbol: str = "SZ000665") -> pd.DataFrame:
    """
    东方财富-个股人气榜-历史趋势及粉丝特征
    https://guba.eastmoney.com/rank/stock?code=000665
    :param symbol: 带市场表示的证券代码
    :type symbol: str
    :return: 个股的历史趋势及粉丝特征
    :rtype: pandas.DataFrame
    """
    url_rank = "https://emappdata.eastmoney.com/stockrank/getHisList"
    payload = {
        "appId": "appId01",
        "globalId": "786e4c21-70dc-435a-93bb-38",
        "marketType": "",
        "srcSecurityCode": symbol,
        "yearType": "5",
    }
    r = requests.post(url_rank, json=payload)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["证券代码"] = symbol
    temp_df.columns = ["时间", "排名", "证券代码"]
    temp_df = temp_df[["时间", "排名", "证券代码"]]

    url_follow = "https://emappdata.eastmoney.com/stockrank/getHisProfileList"
    r = requests.post(url_follow, json=payload)
    data_json = r.json()
    temp_df["新晋粉丝"] = (
        pd.DataFrame(data_json["data"])["newUidRate"].str.strip("%").astype(float) / 100
    )
    temp_df["铁杆粉丝"] = (
        pd.DataFrame(data_json["data"])["oldUidRate"].str.strip("%").astype(float) / 100
    )
    temp_df.sort_values(['时间'], inplace=True)
    return temp_df


def stock_hot_rank_detail_realtime_em(symbol: str = "SZ000665") -> pd.DataFrame:
    """
    东方财富-个股人气榜-实时变动
    https://guba.eastmoney.com/rank/stock?code=000665
    :param symbol: 带市场表示的证券代码
    :type symbol: str
    :return: 实时变动
    :rtype: pandas.DataFrame
    """
    url = "https://emappdata.eastmoney.com/stockrank/getCurrentList"
    payload = {
        "appId": "appId01",
        "globalId": "786e4c21-70dc-435a-93bb-38",
        "marketType": "",
        "srcSecurityCode": symbol,
    }
    r = requests.post(url, json=payload)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["时间", "排名"]
    return temp_df


def stock_hot_keyword_em(symbol: str = "SZ000665") -> pd.DataFrame:
    """
    东方财富-个股人气榜-热门关键词
    https://guba.eastmoney.com/rank/stock?code=000665
    :param symbol: 带市场表示的证券代码
    :type symbol: str
    :return: 热门关键词
    :rtype: pandas.DataFrame
    """
    url = "https://emappdata.eastmoney.com/stockrank/getHotStockRankList"
    payload = {
        "appId": "appId01",
        "globalId": "786e4c21-70dc-435a-93bb-38",
        "srcSecurityCode": symbol,
    }
    r = requests.post(url, json=payload)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    del temp_df["flag"]
    temp_df.columns = ["时间", "股票代码", "概念名称", "概念代码", "热度"]
    return temp_df


def stock_hot_rank_latest_em(symbol: str = "SZ000665") -> pd.DataFrame:
    """
    东方财富-个股人气榜-最新排名
    https://guba.eastmoney.com/rank/stock?code=000665
    :param symbol: 带市场表示的证券代码
    :type symbol: str
    :return: 最新排名
    :rtype: pandas.DataFrame
    """
    url = "https://emappdata.eastmoney.com/stockrank/getCurrentLatest"
    payload = {
        "appId": "appId01",
        "globalId": "786e4c21-70dc-435a-93bb-38",
        "marketType": "",
        "srcSecurityCode": symbol,
    }
    r = requests.post(url, json=payload)
    data_json = r.json()
    temp_df = pd.DataFrame.from_dict(data_json["data"], orient="index")
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["item", "value"]
    return temp_df


def stock_hot_rank_relate_em(symbol: str = "SZ000665") -> pd.DataFrame:
    """
    东方财富-个股人气榜-相关股票
    https://guba.eastmoney.com/rank/stock?code=000665
    :param symbol: 带市场表示的证券代码
    :type symbol: str
    :return: 相关股票
    :rtype: pandas.DataFrame
    """
    url = "https://emappdata.eastmoney.com/stockrank/getFollowStockRankList"
    payload = {
        "appId": "appId01",
        "globalId": "786e4c21-70dc-435a-93bb-38",
        "srcSecurityCode": symbol,
    }
    r = requests.post(url, json=payload)
    data_json = r.json()
    temp_df = pd.DataFrame.from_dict(data_json["data"])
    temp_df.columns = ["时间", "-", "股票代码", "-", "相关股票代码", "涨跌幅", "-"]
    temp_df = temp_df[["时间", "股票代码", "相关股票代码", "涨跌幅"]]
    temp_df["涨跌幅"] = temp_df["涨跌幅"].str.strip("%")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_hot_rank_em_df = stock_hot_rank_em()
    print(stock_hot_rank_em_df)

    stock_hot_rank_detail_em_df = stock_hot_rank_detail_em(symbol="SZ871245")
    print(stock_hot_rank_detail_em_df)

    stock_hot_rank_detail_realtime_em_df = stock_hot_rank_detail_realtime_em(
        symbol="SZ000665"
    )
    print(stock_hot_rank_detail_realtime_em_df)

    stock_hot_keyword_em_df = stock_hot_keyword_em(symbol="SZ000665")
    print(stock_hot_keyword_em_df)

    stock_hot_rank_latest_em_df = stock_hot_rank_latest_em(symbol="SZ000665")
    print(stock_hot_rank_latest_em_df)

    stock_hot_rank_relate_em_df = stock_hot_rank_relate_em(symbol="SZ000665")
    print(stock_hot_rank_relate_em_df)
