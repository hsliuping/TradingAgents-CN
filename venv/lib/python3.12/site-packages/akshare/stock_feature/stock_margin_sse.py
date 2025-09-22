#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/6/14 17:20
Desc: 上海证券交易所-融资融券数据
https://www.sse.com.cn/market/othersdata/margin/sum/
"""

import pandas as pd
import requests


def stock_margin_ratio_pa(date: str = "20231013") -> pd.DataFrame:
    """
    融资融券-标的证券名单及保证金比例查询
    https://stock.pingan.com/static/webinfo/margin/business.html?businessType=0
    :param date: 交易日期
    :type date: str
    :return: 标的证券名单及保证金比例查询
    :rtype: pandas.DataFrame
    """
    url = "https://stock.pingan.com/fss/servlet/fsscoreapp/stockSource/mrgRatio"
    payload = {
        "currentPage": 1,
        "pageSize": 50000,
        "type": "bdzq",
        "setdate": "-".join([date[:4], date[4:6], date[6:]]),
        "stockMes": "",
        "market": "00",
        "appName": "AYLCH5",
        "tokenId": "",
        "appChannel": "LRSP",
        "requestId": "194055910e2075c03e25fabf6ffc5a7f",
        "channel": "pa18",
    }
    r = requests.post(url, json=payload)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["list"])
    temp_df.rename(
        columns={
            "fiMarginRatio": "融资比例",
            "secuCode": "证券代码",
            "secuName": "证券简称",
            "slMarginRatio": "融券比例",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "证券代码",
            "证券简称",
            "融资比例",
            "融券比例",
        ]
    ]
    temp_df["融资比例"] = pd.to_numeric(temp_df["融资比例"], errors="coerce")
    temp_df["融券比例"] = pd.to_numeric(temp_df["融券比例"], errors="coerce")
    return temp_df


def stock_margin_sse(
    start_date: str = "20010106", end_date: str = "20230922"
) -> pd.DataFrame:
    """
    上海证券交易所-融资融券数据-融资融券汇总
    https://www.sse.com.cn/market/othersdata/margin/sum/
    :param start_date: 交易开始日期
    :type start_date: str
    :param end_date: 交易结束日期
    :type end_date: str
    :return: 融资融券汇总
    :rtype: pandas.DataFrame
    """
    url = "https://query.sse.com.cn/marketdata/tradedata/queryMargin.do"
    params = {
        "isPagination": "true",
        "beginDate": start_date,
        "endDate": end_date,
        "tabType": "",
        "stockCode": "",
        "pageHelp.pageSize": "5000",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": "5",
    }
    headers = {
        "Referer": "https://www.sse.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/88.0.4324.150 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"])
    temp_df.columns = [
        "_",
        "信用交易日期",
        "_",
        "融券卖出量",
        "融券余量",
        "融券余量金额",
        "_",
        "_",
        "融资买入额",
        "融资融券余额",
        "融资余额",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "信用交易日期",
            "融资余额",
            "融资买入额",
            "融券余量",
            "融券余量金额",
            "融券卖出量",
            "融资融券余额",
        ]
    ]
    temp_df["融资余额"] = pd.to_numeric(temp_df["融资余额"], errors="coerce")
    temp_df["融资买入额"] = pd.to_numeric(temp_df["融资买入额"], errors="coerce")
    temp_df["融券余量"] = pd.to_numeric(temp_df["融券余量"], errors="coerce")
    temp_df["融券余量金额"] = pd.to_numeric(temp_df["融券余量金额"], errors="coerce")
    temp_df["融券卖出量"] = pd.to_numeric(temp_df["融券卖出量"], errors="coerce")
    temp_df["融资融券余额"] = pd.to_numeric(temp_df["融资融券余额"], errors="coerce")
    return temp_df


def stock_margin_detail_sse(date: str = "20230922") -> pd.DataFrame:
    """
    上海证券交易所-融资融券数据-融资融券明细
    https://www.sse.com.cn/market/othersdata/margin/detail/
    :param date: 交易日期
    :type date: str
    :return: 融资融券明细
    :rtype: pandas.DataFrame
    """
    url = "https://query.sse.com.cn/marketdata/tradedata/queryMargin.do"
    params = {
        "isPagination": "true",
        "tabType": "mxtype",
        "detailsDate": date,
        "stockCode": "",
        "beginDate": "",
        "endDate": "",
        "pageHelp.pageSize": "5000",
        "pageHelp.pageCount": "50",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": "21",
    }
    headers = {
        "Referer": "https://www.sse.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/88.0.4324.150 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"])
    temp_df.columns = [
        "_",
        "信用交易日期",
        "融券偿还量",
        "融券卖出量",
        "融券余量",
        "_",
        "_",
        "融资偿还额",
        "融资买入额",
        "_",
        "融资余额",
        "标的证券简称",
        "标的证券代码",
    ]
    temp_df = temp_df[
        [
            "信用交易日期",
            "标的证券代码",
            "标的证券简称",
            "融资余额",
            "融资买入额",
            "融资偿还额",
            "融券余量",
            "融券卖出量",
            "融券偿还量",
        ]
    ]
    temp_df["融资余额"] = pd.to_numeric(temp_df["融资余额"], errors="coerce")
    temp_df["融资买入额"] = pd.to_numeric(temp_df["融资买入额"], errors="coerce")
    temp_df["融资偿还额"] = pd.to_numeric(temp_df["融资偿还额"], errors="coerce")
    temp_df["融券余量"] = pd.to_numeric(temp_df["融券余量"], errors="coerce")
    temp_df["融券卖出量"] = pd.to_numeric(temp_df["融券卖出量"], errors="coerce")
    temp_df["融券偿还量"] = pd.to_numeric(temp_df["融券偿还量"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_margin_ratio_pa_df = stock_margin_ratio_pa(date="20231013")
    print(stock_margin_ratio_pa_df)

    stock_margin_sse_df = stock_margin_sse(start_date="20010106", end_date="20210401")
    print(stock_margin_sse_df)

    stock_margin_detail_sse_df = stock_margin_detail_sse(date="20230922")
    print(stock_margin_detail_sse_df)
