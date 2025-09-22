#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/3/5 17:00
Desc: 金十数据中心-实时监控-微博舆情报告
https://datacenter.jin10.com/market
报告内容：时间期限可选择2小时、6小时、12小时、1天、1周、1月。
该表格展示的是在对应的时间期限内，个股在微博讨论中的人气排行指数。
红色颜色越深，表明该股票讨论热度越高，其当前的涨幅更大。
绿色颜色越深，表明该股票讨论的热度越低，其当前的跌幅更大。
"""

import time
from typing import Dict

import pandas as pd
import requests


def stock_js_weibo_nlp_time() -> Dict:
    """
    https://datacenter.jin10.com/market
    :return: 特定时间表示的字典
    :rtype: dict
    """
    url = "https://datacenter-api.jin10.com/weibo/config"
    payload = {"_": int(time.time() * 1000)}
    headers = {
        "authority": "datacenter-api.jin10.com",
        "pragma": "no-cache",
        "cache-control": "no-cache",
        "accept": "*/*",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "sec-fetch-dest": "empty",
        "x-csrf-token": "",
        "x-version": "1.0.0",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.116 Safari/537.36",
        "origin": "https://datacenter.jin10.com",
        "sec-fetch-site": "same-site",
        "sec-fetch-mode": "cors",
        "referer": "https://datacenter.jin10.com/market",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    r = requests.get(url, headers=headers, data=payload)
    return r.json()["data"]["timescale"]


def stock_js_weibo_report(time_period: str = "CNHOUR12") -> pd.DataFrame:
    """
    金十数据中心-实时监控-微博舆情报告
    https://datacenter.jin10.com/market
    :param time_period: {'CNHOUR2': '2小时', 'CNHOUR6': '6小时', 'CNHOUR12': '12小时', 'CNHOUR24': '1天', 'CNDAY7': '1周', 'CNDAY30': '1月'}
    :type time_period: str
    :return: 指定时间段的微博舆情报告
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-api.jin10.com/weibo/list"
    payload = {"timescale": time_period, "_": int(time.time() * 1000)}
    headers = {
        "authority": "datacenter-api.jin10.com",
        "pragma": "no-cache",
        "cache-control": "no-cache",
        "accept": "*/*",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "sec-fetch-dest": "empty",
        "x-csrf-token": "",
        "x-version": "1.0.0",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.116 Safari/537.36",
        "origin": "https://datacenter.jin10.com",
        "sec-fetch-site": "same-site",
        "sec-fetch-mode": "cors",
        "referer": "https://datacenter.jin10.com/market",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    r = requests.get(url, params=payload, headers=headers)
    temp_df = pd.DataFrame(r.json()["data"])
    temp_df["rate"] = pd.to_numeric(temp_df["rate"])
    return temp_df


if __name__ == "__main__":
    stock_js_weibo_nlp_time_map = stock_js_weibo_nlp_time()
    print(stock_js_weibo_nlp_time_map)

    get_news_df = stock_js_weibo_report(time_period="CNHOUR6")
    print(get_news_df)
