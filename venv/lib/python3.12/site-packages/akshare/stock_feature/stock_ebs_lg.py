#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/19 15:30
Desc: 乐咕乐股-股债利差
https://legulegu.com/stockdata/equity-bond-spread
"""

import pandas as pd
import requests

from akshare.stock_feature.stock_a_indicator import get_token_lg, get_cookie_csrf


def stock_ebs_lg() -> pd.DataFrame:
    """
    乐咕乐股-股债利差
    https://legulegu.com/stockdata/equity-bond-spread
    :return: 股债利差
    :rtype: pandas.DataFrame
    """
    url = "https://legulegu.com/api/stockdata/equity-bond-spread"
    token = get_token_lg()
    params = {"token": token, "code": "000300.SH"}
    r = requests.get(
        url,
        params=params,
        **get_cookie_csrf(url="https://legulegu.com/stockdata/equity-bond-spread"),
    )
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df.rename(
        columns={
            "date": "日期",
            "close": "沪深300指数",
            "peSpread": "股债利差",
            "peSpreadAverage": "股债利差均线",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "日期",
            "沪深300指数",
            "股债利差",
            "股债利差均线",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["沪深300指数"] = pd.to_numeric(temp_df["沪深300指数"], errors="coerce")
    temp_df["股债利差"] = pd.to_numeric(temp_df["股债利差"], errors="coerce")
    temp_df["股债利差均线"] = pd.to_numeric(temp_df["股债利差均线"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_ebs_lg_df = stock_ebs_lg()
    print(stock_ebs_lg_df)
