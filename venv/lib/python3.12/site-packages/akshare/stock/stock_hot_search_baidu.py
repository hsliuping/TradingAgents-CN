#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/6/16 18:19
Desc: 百度股市通-热搜股票
https://gushitong.baidu.com/hotlist?mainTab=hotSearch&market=all
"""

from datetime import datetime

import pandas as pd
import requests


def stock_hot_search_baidu(
    symbol: str = "A股", date: str = "20250616", time: str = "今日"
):
    """
    百度股市通-热搜股票
    https://gushitong.baidu.com/hotlist?mainTab=hotSearch&market=all
    :param symbol: choice of {"全部", "A股", "港股", "美股"}
    :type symbol: str
    :param date: 日期
    :type date: str
    :param time: time="今日"；choice of {"今日", "1小时"}
    :type time: str
    :return: 热搜股票
    :rtype: pandas.DataFrame
    """
    hour_str = datetime.now().hour
    symbol_map = {
        "全市场": "all",
        "A股": "ab",
        "港股": "hk",
        "美股": "us",
    }
    url = "https://finance.pae.baidu.com/selfselect/listsugrecomm"
    params = {
        "bizType": "wisexmlnew",
        "dsp": "iphone",
        "product": "search",
        "style": "tablelist",
        "market": symbol_map[symbol],
        "type": time,
        "day": date,
        "hour": hour_str,
        "pn": "0",
        "rn": "12",
        "finClientType": "pc",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["Result"]['list']["body"])
    temp_df.rename(columns={
        'name': "名称/代码",
        'pxChangeRate': "涨跌幅",
        'heat': "综合热度",

    }, inplace=True)
    temp_df = temp_df[[
        "名称/代码",
        "涨跌幅",
        "综合热度",
    ]]
    temp_df['综合热度'] = pd.to_numeric(temp_df['综合热度'], errors='coerce')
    return temp_df


if __name__ == "__main__":
    stock_hot_search_baidu_df = stock_hot_search_baidu(
        symbol="A股", date="20250616", time="今日"
    )
    print(stock_hot_search_baidu_df)
