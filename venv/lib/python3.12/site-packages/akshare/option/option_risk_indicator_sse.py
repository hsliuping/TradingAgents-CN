# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/6/27 22:20
Desc: 上海证券交易所-产品-股票期权-期权风险指标
"""

import requests
import pandas as pd


def option_risk_indicator_sse(date: str = "20240626") -> pd.DataFrame:
    """
    上海证券交易所-产品-股票期权-期权风险指标
    http://www.sse.com.cn/assortment/options/risk/
    :param date: 日期; 20150209 开始
    :type date: str
    :return: 期权风险指标
    :rtype: pandas.DataFrame
    """
    url = "http://query.sse.com.cn/commonQuery.do"
    params = {
        "isPagination": "false",
        "trade_date": date,
        "sqlId": "SSE_ZQPZ_YSP_GGQQZSXT_YSHQ_QQFXZB_DATE_L",
        "contractSymbol": "",
    }
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "query.sse.com.cn",
        "Pragma": "no-cache",
        "Referer": "http://www.sse.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/101.0.4951.67 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"])
    temp_df = temp_df[
        [
            "TRADE_DATE",
            "SECURITY_ID",
            "CONTRACT_ID",
            "CONTRACT_SYMBOL",
            "DELTA_VALUE",
            "THETA_VALUE",
            "GAMMA_VALUE",
            "VEGA_VALUE",
            "RHO_VALUE",
            "IMPLC_VOLATLTY",
        ]
    ]
    temp_df["TRADE_DATE"] = pd.to_datetime(
        temp_df["TRADE_DATE"], errors="coerce"
    ).dt.date
    temp_df["DELTA_VALUE"] = pd.to_numeric(temp_df["DELTA_VALUE"], errors="coerce")
    temp_df["THETA_VALUE"] = pd.to_numeric(temp_df["THETA_VALUE"], errors="coerce")
    temp_df["GAMMA_VALUE"] = pd.to_numeric(temp_df["GAMMA_VALUE"], errors="coerce")
    temp_df["VEGA_VALUE"] = pd.to_numeric(temp_df["VEGA_VALUE"], errors="coerce")
    temp_df["RHO_VALUE"] = pd.to_numeric(temp_df["RHO_VALUE"], errors="coerce")
    temp_df["IMPLC_VOLATLTY"] = pd.to_numeric(
        temp_df["IMPLC_VOLATLTY"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    option_risk_indicator_sse_df = option_risk_indicator_sse(date="20240626")
    print(option_risk_indicator_sse_df)
