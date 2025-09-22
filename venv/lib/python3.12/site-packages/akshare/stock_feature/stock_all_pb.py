#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/4/11 20:40
Desc: 全部A股-等权重市净率、中位数市净率
https://www.legulegu.com/stockdata/all-pb
"""

import pandas as pd
import requests

from akshare.stock_feature.stock_a_indicator import get_token_lg, get_cookie_csrf


def stock_a_all_pb() -> pd.DataFrame:
    """
    全部A股-等权重市净率、中位数市净率
    https://legulegu.com/stockdata/all-pb
    :return: 全部A股-等权重市盈率、中位数市盈率
    :rtype: pandas.DataFrame
    """
    url = "https://legulegu.com/api/stock-data/market-index-pb"
    params = {
        "marketId": "ALL",
        "token": get_token_lg(),
    }
    r = requests.get(
        url,
        params=params,
        **get_cookie_csrf(url="https://legulegu.com/stockdata/all-pb"),
    )
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["date"] = (
        pd.to_datetime(temp_df["date"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    del temp_df["weightingAveragePB"]
    return temp_df


if __name__ == "__main__":
    stock_a_all_pb_df = stock_a_all_pb()
    print(stock_a_all_pb_df)
