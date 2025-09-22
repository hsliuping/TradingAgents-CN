#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/17 19:00
Desc: 数库-A股新闻情绪指数
https://www.chinascope.com/reasearch.html
"""

import pandas as pd
import requests


def index_news_sentiment_scope() -> pd.DataFrame:
    """
    数库-A股新闻情绪指数
    https://www.chinascope.com/reasearch.html
    :return: A股新闻情绪指数
    :rtype: pandas.DataFrame
    """
    url = "https://www.chinascope.com/inews/senti/index"
    params = {"period": "YEAR"}
    r = requests.get(url=url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json)
    temp_df.rename(
        columns={
            "tradeDate": "日期",
            "maIndex1": "市场情绪指数",
            "marketClose": "沪深300指数",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "日期",
            "市场情绪指数",
            "沪深300指数",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["市场情绪指数"] = pd.to_numeric(temp_df["市场情绪指数"], errors="coerce")
    temp_df["沪深300指数"] = pd.to_numeric(temp_df["沪深300指数"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    index_news_sentiment_scope_df = index_news_sentiment_scope()
    print(index_news_sentiment_scope_df)
