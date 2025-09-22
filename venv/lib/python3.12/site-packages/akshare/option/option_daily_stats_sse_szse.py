# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/6/27 22:20
Desc: 上海证券交易所-产品-股票期权-每日统计
https://www.sse.com.cn/assortment/options/date/
深圳证券交易所-市场数据-期权数据-日度概况
https://investor.szse.cn/market/option/day/index.html
"""

import pandas as pd
import requests


def option_daily_stats_sse(date: str = "20240626") -> pd.DataFrame:
    """
    上海证券交易所-产品-股票期权-每日统计
    https://www.sse.com.cn/assortment/options/date/
    :param date: 交易日
    :type date: str
    :return: 每日统计
    :rtype: pandas.DataFrame
    """
    url = "http://query.sse.com.cn/commonQuery.do"
    params = {
        "isPagination": "false",
        "sqlId": "COMMON_SSE_ZQPZ_YSP_QQ_SJTJ_MRTJ_CX",
        "tradeDate": date,
    }
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "query.sse.com.cn",
        "Pragma": "no-cache",
        "Referer": "https://www.sse.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/101.0.4951.67 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"])
    temp_df.rename(
        columns={
            "CONTRACT_VOLUME": "合约数量",
            "CALL_VOLUME": "认购成交量",
            "LEAVES_QTY": "未平仓合约总数",
            "CP_RATE": "认沽/认购",
            "PUT_VOLUME": "认沽成交量",
            "TRADE_DATE": "交易日",
            "TOTAL_MONEY": "总成交额",
            "TOTAL_VOLUME": "总成交量",
            "SECURITY_CODE": "合约标的代码",
            "LEAVES_CALL_QTY": "未平仓认购合约数",
            "LEAVES_PUT_QTY": "未平仓认沽合约数",
            "SECURITY_ABBR": "合约标的名称",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "合约标的代码",
            "合约标的名称",
            "合约数量",
            "总成交额",
            "总成交量",
            "认购成交量",
            "认沽成交量",
            "认沽/认购",
            "未平仓合约总数",
            "未平仓认购合约数",
            "未平仓认沽合约数",
            "交易日",
        ]
    ]
    temp_df["交易日"] = pd.to_datetime(temp_df["交易日"], errors="coerce").dt.date
    for item in temp_df.columns[2:-1]:
        temp_df[item] = temp_df[item].str.replace(",", "")
        temp_df[item] = pd.to_numeric(temp_df[item], errors="coerce")
    return temp_df


def option_daily_stats_szse(date: str = "20240626") -> pd.DataFrame:
    """
    深圳证券交易所-市场数据-期权数据-日度概况
    https://investor.szse.cn/market/option/day/index.html
    :param date: 交易日
    :type date: str
    :return: 每日统计
    :rtype: pandas.DataFrame
    """
    url = "https://investor.szse.cn/api/report/ShowReport/data"
    params = {
        "SHOWTYPE": "JSON",
        "CATALOGID": "ysprdzb",
        "TABKEY": "tab1",
        "txtQueryDate": "-".join([date[:4], date[4:6], date[6:]]),
        "random": "0.0652692406565949",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json[0]["data"])
    temp_df.rename(
        columns={
            "bddm": "合约标的代码",
            "bdmc": "合约标的名称",
            "cjl": "成交量",
            "rccjl": "认购成交量",
            "rpcjl": "认沽成交量",
            "rcrpccb": "认沽/认购持仓比",
            "wpchyzs": "未平仓合约总数",
            "wpcrchys": "未平仓认购合约数",
            "wpcrphys": "未平仓认沽合约数",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "合约标的代码",
            "合约标的名称",
            "成交量",
            "认购成交量",
            "认沽成交量",
            "认沽/认购持仓比",
            "未平仓合约总数",
            "未平仓认购合约数",
            "未平仓认沽合约数",
        ]
    ]
    temp_df["交易日"] = "-".join([date[:4], date[4:6], date[6:]])
    temp_df["交易日"] = pd.to_datetime(temp_df["交易日"], errors="coerce").dt.date
    for item in temp_df.columns[2:-1]:
        temp_df[item] = temp_df[item].str.replace(",", "")
        temp_df[item] = pd.to_numeric(temp_df[item], errors="coerce")
    return temp_df


if __name__ == "__main__":
    option_daily_stats_sse_df = option_daily_stats_sse(date="20240626")
    print(option_daily_stats_sse_df)

    option_daily_stats_szse_df = option_daily_stats_szse(date="20240626")
    print(option_daily_stats_szse_df)
