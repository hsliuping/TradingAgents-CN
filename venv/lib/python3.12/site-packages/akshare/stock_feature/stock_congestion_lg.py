#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/4/7 15:05
Desc: 乐咕乐股-大盘拥挤度
https://legulegu.com/stockdata/ashares-congestion
"""

import pandas as pd
import requests

from akshare.stock_feature.stock_a_indicator import get_token_lg, get_cookie_csrf


def stock_a_congestion_lg() -> pd.DataFrame:
    """
    乐咕乐股-大盘拥挤度
    https://legulegu.com/stockdata/ashares-congestion
    :return: 大盘拥挤度
    :rtype: pandas.DataFrame
    """
    url = "https://legulegu.com/api/stockdata/ashares-congestion"
    token = get_token_lg()
    params = {"token": token}
    r = requests.get(
        url,
        params=params,
        **get_cookie_csrf(url="https://legulegu.com/stockdata/ashares-congestion"),
    )
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["items"])
    temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
    temp_df = temp_df[
        [
            "date",
            "close",
            "congestion",
        ]
    ]
    temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    temp_df["congestion"] = pd.to_numeric(temp_df["congestion"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_a_congestion_lg_df = stock_a_congestion_lg()
    print(stock_a_congestion_lg_df)
