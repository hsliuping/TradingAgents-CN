#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/3/5 18:12
Desc: 百度股市通-外汇-行情榜单
https://gushitong.baidu.com/top/foreign-common-%E5%B8%B8%E7%94%A8
"""

import http.client
import json
import urllib

import pandas as pd


def fx_quote_baidu(symbol: str = "人民币") -> pd.DataFrame:
    """
    百度股市通-外汇-行情榜单
    https://gushitong.baidu.com/top/foreign-common-%E5%B8%B8%E7%94%A8
    :param symbol: choice of {"人民币", 美元"}
    :type symbol: str
    :return: 外汇行情数据
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "人民币": "rmb",
        "美元": "dollar",
    }
    num = 0
    out_df = pd.DataFrame()
    while True:
        try:
            conn = http.client.HTTPSConnection("finance.pae.baidu.com")
            params = {
                "pn": num,
                "rn": "20",
                "type": symbol_map[symbol],
                "finClientType": "pc",
            }
            conn.request("GET", f"/api/getforeignrank?{urllib.parse.urlencode(params)}")
            res = conn.getresponse()
            data = res.read()
            data_json = json.loads(data.decode("utf-8"))
            temp_df = pd.DataFrame(data_json["Result"])
            temp_list = []
            for item in temp_df["list"]:
                temp_list.append(list(pd.DataFrame(item).T.iloc[1, :].values))
            value_df = pd.DataFrame(
                temp_list, columns=pd.DataFrame(item).T.iloc[0, :].values
            )
            big_df = pd.concat([temp_df, value_df], axis=1)
            del big_df["market"]
            del big_df["list"]
            del big_df["status"]
            del big_df["icon1"]
            del big_df["icon2"]
            big_df.columns = ["代码", "名称", "最新价", "涨跌额", "涨跌幅"]
            big_df["最新价"] = pd.to_numeric(big_df["最新价"])
            big_df["涨跌额"] = pd.to_numeric(big_df["涨跌额"])
            big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"].str.strip("%")) / 100
            out_df = pd.concat([out_df, big_df], ignore_index=True)
            num = num + 20
        except:  # noqa: E722
            break
    return out_df


if __name__ == "__main__":
    fx_quote_baidu_df = fx_quote_baidu(symbol="人民币")
    print(fx_quote_baidu_df)
