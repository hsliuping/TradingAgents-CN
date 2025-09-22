#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/11 17:40
Desc: 申万宏源研究-申万指数-指数发布-基金指数-实时行情
https://www.swsresearch.com/institute_sw/allIndex/releasedIndex
"""

import pandas as pd
import requests

from akshare.utils.cons import headers


def index_realtime_fund_sw(symbol: str = "基础一级") -> pd.DataFrame:
    """
    申万宏源研究-申万指数-指数发布-基金指数-实时行情
    https://www.swsresearch.com/institute_sw/allIndex/releasedIndex
    :param symbol: choice of {"基础一级", "基础二级", "基础三级", "特色指数"}
    :type symbol: str
    :return: 基金指数-实时行情
    :rtype: pandas.DataFrame
    """
    url = "https://www.swsresearch.com/insWechatSw/fundIndex/pageList"
    payload = {
        "pageNo": 1,
        "pageSize": 50,
        "indexTypeName": symbol,
        "sortField": "",
        "rule": "",
        "indexType": 1,
    }
    r = requests.post(url, json=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["list"])
    temp_df.rename(
        columns={
            "swIndexCode": "指数代码",
            "swIndexName": "指数名称",
            "lastCloseIndex": "昨收盘",
            "lastMarkup": "日涨跌幅",
            "yearMarkup": "年涨跌幅",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "指数代码",
            "指数名称",
            "昨收盘",
            "日涨跌幅",
            "年涨跌幅",
        ]
    ]
    temp_df["昨收盘"] = pd.to_numeric(temp_df["昨收盘"], errors="coerce")
    temp_df["日涨跌幅"] = pd.to_numeric(temp_df["日涨跌幅"], errors="coerce")
    temp_df["年涨跌幅"] = pd.to_numeric(temp_df["年涨跌幅"], errors="coerce")
    return temp_df


def index_hist_fund_sw(symbol: str = "807200", period: str = "day") -> pd.DataFrame:
    """
    申万宏源研究-申万指数-指数发布-基金指数-历史行情
    https://www.swsresearch.com/institute_sw/allIndex/releasedIndex/fundDetail?code=807100
    :param symbol: 基金指数代码
    :type symbol: str
    :param period: 周期
    :type period: str
    :return: 历史行情
    :rtype: pandas.DataFrame
    """
    period_map = {
        "day": "DAY",
        "week": "WEEK",
        "month": "MONTH",
    }
    url = "https://www.swsresearch.com/insWechatSw/fundIndex/getFundKChartData"
    payload = {"swIndexCode": symbol, "type": period_map[period]}
    r = requests.post(url, json=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.rename(
        columns={
            "bargaindate": "日期",
            "swIndexName": "指数名称",
            "swindexcode": "指数代码",
            "closeindex": "收盘指数",
            "maxindex": "最高指数",
            "minindex": "最低指数",
            "openindex": "开盘指数",
            "markup": "涨跌幅",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "日期",
            "收盘指数",
            "开盘指数",
            "最高指数",
            "最低指数",
            "涨跌幅",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["收盘指数"] = pd.to_numeric(temp_df["收盘指数"], errors="coerce")
    temp_df["最高指数"] = pd.to_numeric(temp_df["最高指数"], errors="coerce")
    temp_df["最低指数"] = pd.to_numeric(temp_df["最低指数"], errors="coerce")
    temp_df["开盘指数"] = pd.to_numeric(temp_df["开盘指数"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    index_realtime_fund_sw_df = index_realtime_fund_sw(symbol="基础一级")
    print(index_realtime_fund_sw_df)

    index_realtime_fund_sw_df = index_realtime_fund_sw(symbol="基础二级")
    print(index_realtime_fund_sw_df)

    index_realtime_fund_sw_df = index_realtime_fund_sw(symbol="基础三级")
    print(index_realtime_fund_sw_df)

    index_realtime_fund_sw_df = index_realtime_fund_sw(symbol="特色指数")
    print(index_realtime_fund_sw_df)

    index_hist_fund_sw_df = index_hist_fund_sw(symbol="807200", period="day")
    print(index_hist_fund_sw_df)

    index_hist_fund_sw_df = index_hist_fund_sw(symbol="807200", period="week")
    print(index_hist_fund_sw_df)

    index_hist_fund_sw_df = index_hist_fund_sw(symbol="807200", period="month")
    print(index_hist_fund_sw_df)
