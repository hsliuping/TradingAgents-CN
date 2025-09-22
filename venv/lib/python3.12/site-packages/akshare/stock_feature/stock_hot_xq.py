# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/1/7 17:00
Desc: 雪球-沪深股市-热度排行榜
https://xueqiu.com/hq
"""

import math

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_hot_follow_xq(symbol: str = "最热门") -> pd.DataFrame:
    """
    雪球-沪深股市-热度排行榜-关注排行榜
    https://xueqiu.com/hq
    :param symbol: choice of {"本周新增", "最热门"}
    :type symbol: str
    :return: 关注排行榜
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "本周新增": "follow7d",
        "最热门": "follow",
    }
    url = "https://xueqiu.com/service/v5/stock/screener/screen"
    params = {
        "category": "CN",
        "size": "200",
        "order": "desc",
        "order_by": symbol_map[symbol],
        "only_count": "0",
        "page": "1",
    }
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "xueqiu.com",
        "Pragma": "no-cache",
        "Referer": "https://xueqiu.com/hq",
        "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="100", "Google Chrome";v="100"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    total_num = data_json["data"]["count"]
    total_page = math.ceil(total_num / 200)
    tqdm = get_tqdm()
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        try:
            temp_df = pd.DataFrame(data_json["data"]["list"])
        except TypeError:
            temp_df = pd.DataFrame()
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    if symbol == "本周新增":
        big_df = big_df[
            [
                "symbol",
                "name",
                "follow7d",
                "current",
            ]
        ]
    else:
        big_df = big_df[
            [
                "symbol",
                "name",
                "follow",
                "current",
            ]
        ]
    big_df.columns = [
        "股票代码",
        "股票简称",
        "关注",
        "最新价",
    ]
    big_df["关注"] = pd.to_numeric(big_df["关注"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    return big_df


def stock_hot_tweet_xq(symbol: str = "最热门") -> pd.DataFrame:
    """
    雪球-沪深股市-热度排行榜-讨论排行榜
    https://xueqiu.com/hq
    :param symbol: choice of {"本周新增", "最热门"}
    :type symbol: str
    :return: 讨论排行榜
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "本周新增": "tweet7d",
        "最热门": "tweet",
    }
    url = "https://xueqiu.com/service/v5/stock/screener/screen"
    params = {
        "category": "CN",
        "size": "200",
        "order": "desc",
        "order_by": symbol_map[symbol],
        "only_count": "0",
        "page": "1",
    }
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "xueqiu.com",
        "Pragma": "no-cache",
        "Referer": "https://xueqiu.com/hq",
        "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="100", "Google Chrome";v="100"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    total_num = data_json["data"]["count"]
    total_page = math.ceil(total_num / 200)
    tqdm = get_tqdm()
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        try:
            temp_df = pd.DataFrame(data_json["data"]["list"])
        except TypeError:
            temp_df = pd.DataFrame()
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    if symbol == "本周新增":
        big_df = big_df[
            [
                "symbol",
                "name",
                "tweet7d",
                "current",
            ]
        ]
    else:
        big_df = big_df[
            [
                "symbol",
                "name",
                "tweet",
                "current",
            ]
        ]
    big_df.columns = [
        "股票代码",
        "股票简称",
        "关注",
        "最新价",
    ]
    big_df["关注"] = pd.to_numeric(big_df["关注"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    return big_df


def stock_hot_deal_xq(symbol: str = "最热门") -> pd.DataFrame:
    """
    雪球-沪深股市-热度排行榜-分享交易排行榜
    https://xueqiu.com/hq
    :param symbol: choice of {"本周新增", "最热门"}
    :type symbol: str
    :return: 分享交易排行榜
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "本周新增": "deal7d",
        "最热门": "deal",
    }
    url = "https://xueqiu.com/service/v5/stock/screener/screen"
    params = {
        "category": "CN",
        "size": "10000",
        "order": "desc",
        "order_by": symbol_map[symbol],
        "only_count": "0",
        "page": "1",
    }
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "xueqiu.com",
        "Pragma": "no-cache",
        "Referer": "https://xueqiu.com/hq",
        "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="100", "Google Chrome";v="100"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    total_num = data_json["data"]["count"]
    total_page = math.ceil(total_num / 200)
    tqdm = get_tqdm()
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        try:
            temp_df = pd.DataFrame(data_json["data"]["list"])
        except TypeError:
            temp_df = pd.DataFrame()
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    if symbol == "本周新增":
        big_df = big_df[
            [
                "symbol",
                "name",
                "deal7d",
                "current",
            ]
        ]
    else:
        big_df = big_df[
            [
                "symbol",
                "name",
                "deal",
                "current",
            ]
        ]
    big_df.columns = [
        "股票代码",
        "股票简称",
        "关注",
        "最新价",
    ]
    big_df["关注"] = pd.to_numeric(big_df["关注"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    return big_df


if __name__ == "__main__":
    stock_hot_follow_xq_df = stock_hot_follow_xq(symbol="本周新增")
    print(stock_hot_follow_xq_df)

    stock_hot_follow_xq_df = stock_hot_follow_xq(symbol="最热门")
    print(stock_hot_follow_xq_df)

    stock_hot_tweet_xq_df = stock_hot_tweet_xq(symbol="本周新增")
    print(stock_hot_tweet_xq_df)

    stock_hot_tweet_xq_df = stock_hot_tweet_xq(symbol="最热门")
    print(stock_hot_tweet_xq_df)

    stock_hot_deal_xq_df = stock_hot_deal_xq(symbol="本周新增")
    print(stock_hot_deal_xq_df)

    stock_hot_deal_xq_df = stock_hot_deal_xq(symbol="最热门")
    print(stock_hot_deal_xq_df)
