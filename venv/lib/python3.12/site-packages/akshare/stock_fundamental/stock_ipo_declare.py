#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/1/7 17:02
Desc: 东方财富网-数据中心-新股申购-首发申报信息-首发申报企业信息
https://data.eastmoney.com/xg/xg/sbqy.html
"""

import pandas as pd
import requests

from akshare.utils import demjson


def stock_ipo_declare() -> pd.DataFrame:
    """
    东方财富网-数据中心-新股申购-首发申报信息-首发申报企业信息
    https://data.eastmoney.com/xg/xg/sbqy.html
    :return: 首发申报企业信息
    :rtype: pandas.DataFrame
    """
    url = "https://datainterface.eastmoney.com/EM_DataCenter/JS.aspx"
    params = {
        "st": "1",
        "sr": "-1",
        "ps": "500",
        "p": "1",
        "type": "NS",
        "sty": "NSFR",
        "js": "({data:[(x)],pages:(pc)})",
        "mkt": "1",
        "fd": "2021-04-02",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[1:-1])
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1
    temp_df.columns = [
        "序号",
        "会计师事务所",
        "_",
        "保荐机构",
        "_",
        "律师事务所",
        "_",
        "_",
        "拟上市地",
        "_",
        "_",
        "备注",
        "申报企业",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "序号",
            "申报企业",
            "拟上市地",
            "保荐机构",
            "会计师事务所",
            "律师事务所",
            "备注",
        ]
    ]
    return temp_df


if __name__ == "__main__":
    stock_ipo_declare_df = stock_ipo_declare()
    print(stock_ipo_declare_df)
