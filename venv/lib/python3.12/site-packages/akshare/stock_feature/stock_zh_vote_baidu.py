#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/10/10 17:26
Desc: 百度股市通- A 股或指数-股评-投票
https://gushitong.baidu.com/index/ab-000001
"""

import requests
import pandas as pd


def stock_zh_vote_baidu(
    symbol: str = "000001", indicator: str = "指数"
) -> pd.DataFrame:
    """
    百度股市通- A 股或指数-股评-投票
    https://gushitong.baidu.com/index/ab-000001
    :param symbol: 股票代码
    :type symbol: str
    :param indicator: choice of {"指数", "股票"}
    :type indicator: str
    :return: 投票数据
    :rtype: pandas.DataFrame
    """
    indicator_map = {"股票": "stock", "指数": "index"}
    url = "https://finance.pae.baidu.com/vapi/v1/stockvoterecords"
    params = {
        "code": symbol,
        "market": "ab",
        "finance_type": indicator_map[indicator],
        "select_type": "week",
        "from_smart_app": "0",
        "method": "query",
        "finClientType": "pc",
    }
    temp_list = []
    for item_period in ["day", "week", "month", "year"]:
        params.update({"select_type": item_period})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_list.append(
            [
                item
                for item in data_json["Result"]["voteRecords"]["voteRes"]
                if item["type"] == item_period
            ][0]
        )
    temp_df = pd.DataFrame(temp_list)
    temp_df.columns = ["周期", "-", "看涨", "看跌", "看涨比例", "看跌比例"]
    temp_df = temp_df[["周期", "看涨", "看跌", "看涨比例", "看跌比例"]]
    return temp_df


if __name__ == "__main__":
    stock_zh_vote_baidu_df = stock_zh_vote_baidu(symbol="000001", indicator="指数")
    print(stock_zh_vote_baidu_df)
