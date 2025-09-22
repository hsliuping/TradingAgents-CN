# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/12/26 18:00
Desc: 上海金属网-快讯
https://www.shmet.com/newsFlash/newsFlash.html?searchKeyword=
"""

import pandas as pd
import requests


def futures_news_shmet(symbol: str = "全部") -> pd.DataFrame:
    """
    上海金属网-快讯
    https://www.shmet.com/newsFlash/newsFlash.html?searchKeyword=
    :param symbol: choice of {"全部", "要闻", "VIP", "财经", "铜", "铝", "铅", "锌", "镍", "锡", "贵金属", "小金属"}
    :type symbol: str
    :return: 上海金属网-快讯
    :rtype: pandas.DataFrame
    """
    url = "https://www.shmet.com/api/rest/news/queryNewsflashList"
    if symbol == "全部":
        payload = {"currentPage": 1, "pageSize": 100}
    else:
        symbol_map = {
            "要闻": "0",
            "VIP": "100",
            "财经": "999",
            "铜": "1002",
            "铝": "1003",
            "铅": "1005",
            "锌": "1004",
            "镍": "1006",
            "锡": "1007",
            "贵金属": "1008",
            "小金属": "1009",
        }
        payload = {
            "currentPage": 1,
            "pageSize": 2000,
            "content": "",
            "flashTag": symbol_map[symbol],
        }
    r = requests.post(url, json=payload)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["dataList"])
    temp_df.columns = [
        "-",
        "-",
        "-",
        "发布时间",
        "-",
        "内容",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    temp_df = temp_df[
        [
            "发布时间",
            "内容",
        ]
    ]
    temp_df["发布时间"] = pd.to_datetime(
        temp_df["发布时间"], unit="ms", utc=True
    ).dt.tz_convert("Asia/Shanghai")
    temp_df.sort_values(["发布时间"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


if __name__ == "__main__":
    futures_news_shmet_df = futures_news_shmet(symbol="铜")
    print(futures_news_shmet_df)

    for item in [
        "全部",
        "要闻",
        "VIP",
        "财经",
        "铜",
        "铝",
        "铅",
        "锌",
        "镍",
        "锡",
        "贵金属",
        "小金属",
    ]:
        futures_news_shmet_df = futures_news_shmet(symbol=item)
        print(futures_news_shmet_df)
