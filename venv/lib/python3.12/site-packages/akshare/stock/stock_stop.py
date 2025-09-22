#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/2/24 18:33
Desc: 两网及退市
https://quote.eastmoney.com/center/gridlist.html#staq_net_board
"""

import pandas as pd
import requests


def stock_staq_net_stop() -> pd.DataFrame:
    """
    东方财富网-行情中心-沪深个股-两网及退市
    https://quote.eastmoney.com/center/gridlist.html#staq_net_board
    :return: 两网及退市
    :rtype: pandas.DataFrame
    """
    url = "https://5.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "50000",
        "po": "1",
        "np": "2",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:0 s:3",
        "fields": "f12,f14",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["diff"]).T
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1
    temp_df.columns = ["序号", "代码", "名称"]
    return temp_df


if __name__ == "__main__":
    stock_staq_net_stop_df = stock_staq_net_stop()
    print(stock_staq_net_stop_df)
