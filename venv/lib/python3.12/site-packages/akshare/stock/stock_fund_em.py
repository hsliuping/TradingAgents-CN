#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/10 19:00
Desc: 东方财富网-数据中心-资金流向
https://data.eastmoney.com/zjlx/detail.html
"""

import math
import time
from functools import lru_cache

import pandas as pd
import requests

from akshare.utils.func import fetch_paginated_data
from akshare.utils.tqdm import get_tqdm


def stock_individual_fund_flow(
    stock: str = "600094", market: str = "sh"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-资金流向-个股
    https://data.eastmoney.com/zjlx/detail.html
    :param stock: 股票代码
    :type stock: str
    :param market: 股票市场; 上海证券交易所: sh, 深证证券交易所: sz, 北京证券交易所: bj;
    :type market: str
    :return: 近期个股的资金流数据
    :rtype: pandas.DataFrame
    """
    market_map = {"sh": 1, "sz": 0, "bj": 0}
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
    }
    params = {
        "lmt": "0",
        "klt": "101",
        "secid": f"{market_map[market]}.{stock}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "_": int(time.time() * 1000),
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    content_list = data_json["data"]["klines"]
    temp_df = pd.DataFrame([item.split(",") for item in content_list])
    temp_df.columns = [
        "日期",
        "主力净流入-净额",
        "小单净流入-净额",
        "中单净流入-净额",
        "大单净流入-净额",
        "超大单净流入-净额",
        "主力净流入-净占比",
        "小单净流入-净占比",
        "中单净流入-净占比",
        "大单净流入-净占比",
        "超大单净流入-净占比",
        "收盘价",
        "涨跌幅",
        "-",
        "-",
    ]
    temp_df = temp_df[
        [
            "日期",
            "收盘价",
            "涨跌幅",
            "主力净流入-净额",
            "主力净流入-净占比",
            "超大单净流入-净额",
            "超大单净流入-净占比",
            "大单净流入-净额",
            "大单净流入-净占比",
            "中单净流入-净额",
            "中单净流入-净占比",
            "小单净流入-净额",
            "小单净流入-净占比",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["主力净流入-净额"] = pd.to_numeric(
        temp_df["主力净流入-净额"], errors="coerce"
    )
    temp_df["小单净流入-净额"] = pd.to_numeric(
        temp_df["小单净流入-净额"], errors="coerce"
    )
    temp_df["中单净流入-净额"] = pd.to_numeric(
        temp_df["中单净流入-净额"], errors="coerce"
    )
    temp_df["大单净流入-净额"] = pd.to_numeric(
        temp_df["大单净流入-净额"], errors="coerce"
    )
    temp_df["超大单净流入-净额"] = pd.to_numeric(
        temp_df["超大单净流入-净额"], errors="coerce"
    )
    temp_df["主力净流入-净占比"] = pd.to_numeric(
        temp_df["主力净流入-净占比"], errors="coerce"
    )
    temp_df["小单净流入-净占比"] = pd.to_numeric(
        temp_df["小单净流入-净占比"], errors="coerce"
    )
    temp_df["中单净流入-净占比"] = pd.to_numeric(
        temp_df["中单净流入-净占比"], errors="coerce"
    )
    temp_df["大单净流入-净占比"] = pd.to_numeric(
        temp_df["大单净流入-净占比"], errors="coerce"
    )
    temp_df["超大单净流入-净占比"] = pd.to_numeric(
        temp_df["超大单净流入-净占比"], errors="coerce"
    )
    temp_df["收盘价"] = pd.to_numeric(temp_df["收盘价"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    return temp_df


def stock_individual_fund_flow_rank(indicator: str = "5日") -> pd.DataFrame:
    """
    东方财富网-数据中心-资金流向-排名
    https://data.eastmoney.com/zjlx/detail.html
    :param indicator: choice of {"今日", "3日", "5日", "10日"}
    :type indicator: str
    :return: 指定 indicator 资金流向排行
    :rtype: pandas.DataFrame
    """
    indicator_map = {
        "今日": [
            "f62",
            "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124",
        ],
        "3日": [
            "f267",
            "f12,f14,f2,f127,f267,f268,f269,f270,f271,f272,f273,f274,f275,f276,f257,f258,f124",
        ],
        "5日": [
            "f164",
            "f12,f14,f2,f109,f164,f165,f166,f167,f168,f169,f170,f171,f172,f173,f257,f258,f124",
        ],
        "10日": [
            "f174",
            "f12,f14,f2,f160,f174,f175,f176,f177,f178,f179,f180,f181,f182,f183,f260,f261,f124",
        ],
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "fid": indicator_map[indicator][0],
        "po": "1",
        "pz": "100",
        "pn": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fs": "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2",
        "fields": indicator_map[indicator][1],
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = math.ceil(data_json["data"]["total"] / 100)
    temp_list = []
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pn": page,
            }
        )
        r = requests.get(url, params=params, timeout=15)
        data_json = r.json()
        inner_temp_df = pd.DataFrame(data_json["data"]["diff"])
        temp_list.append(inner_temp_df)
    temp_df = pd.concat(temp_list, ignore_index=True)
    temp_df.reset_index(inplace=True)
    temp_df["index"] = range(1, len(temp_df) + 1)
    if indicator == "今日":
        temp_df.columns = [
            "序号",
            "最新价",
            "今日涨跌幅",
            "代码",
            "名称",
            "今日主力净流入-净额",
            "今日超大单净流入-净额",
            "今日超大单净流入-净占比",
            "今日大单净流入-净额",
            "今日大单净流入-净占比",
            "今日中单净流入-净额",
            "今日中单净流入-净占比",
            "今日小单净流入-净额",
            "今日小单净流入-净占比",
            "_",
            "今日主力净流入-净占比",
            "_",
            "_",
            "_",
        ]
        temp_df = temp_df[
            [
                "序号",
                "代码",
                "名称",
                "最新价",
                "今日涨跌幅",
                "今日主力净流入-净额",
                "今日主力净流入-净占比",
                "今日超大单净流入-净额",
                "今日超大单净流入-净占比",
                "今日大单净流入-净额",
                "今日大单净流入-净占比",
                "今日中单净流入-净额",
                "今日中单净流入-净占比",
                "今日小单净流入-净额",
                "今日小单净流入-净占比",
            ]
        ]
    elif indicator == "3日":
        temp_df.columns = [
            "序号",
            "最新价",
            "代码",
            "名称",
            "_",
            "3日涨跌幅",
            "_",
            "_",
            "_",
            "3日主力净流入-净额",
            "3日主力净流入-净占比",
            "3日超大单净流入-净额",
            "3日超大单净流入-净占比",
            "3日大单净流入-净额",
            "3日大单净流入-净占比",
            "3日中单净流入-净额",
            "3日中单净流入-净占比",
            "3日小单净流入-净额",
            "3日小单净流入-净占比",
        ]
        temp_df = temp_df[
            [
                "序号",
                "代码",
                "名称",
                "最新价",
                "3日涨跌幅",
                "3日主力净流入-净额",
                "3日主力净流入-净占比",
                "3日超大单净流入-净额",
                "3日超大单净流入-净占比",
                "3日大单净流入-净额",
                "3日大单净流入-净占比",
                "3日中单净流入-净额",
                "3日中单净流入-净占比",
                "3日小单净流入-净额",
                "3日小单净流入-净占比",
            ]
        ]
    elif indicator == "5日":
        temp_df.columns = [
            "序号",
            "最新价",
            "代码",
            "名称",
            "5日涨跌幅",
            "_",
            "5日主力净流入-净额",
            "5日主力净流入-净占比",
            "5日超大单净流入-净额",
            "5日超大单净流入-净占比",
            "5日大单净流入-净额",
            "5日大单净流入-净占比",
            "5日中单净流入-净额",
            "5日中单净流入-净占比",
            "5日小单净流入-净额",
            "5日小单净流入-净占比",
            "_",
            "_",
            "_",
        ]
        temp_df = temp_df[
            [
                "序号",
                "代码",
                "名称",
                "最新价",
                "5日涨跌幅",
                "5日主力净流入-净额",
                "5日主力净流入-净占比",
                "5日超大单净流入-净额",
                "5日超大单净流入-净占比",
                "5日大单净流入-净额",
                "5日大单净流入-净占比",
                "5日中单净流入-净额",
                "5日中单净流入-净占比",
                "5日小单净流入-净额",
                "5日小单净流入-净占比",
            ]
        ]
    elif indicator == "10日":
        temp_df.columns = [
            "序号",
            "最新价",
            "代码",
            "名称",
            "_",
            "10日涨跌幅",
            "10日主力净流入-净额",
            "10日主力净流入-净占比",
            "10日超大单净流入-净额",
            "10日超大单净流入-净占比",
            "10日大单净流入-净额",
            "10日大单净流入-净占比",
            "10日中单净流入-净额",
            "10日中单净流入-净占比",
            "10日小单净流入-净额",
            "10日小单净流入-净占比",
            "_",
            "_",
            "_",
        ]
        temp_df = temp_df[
            [
                "序号",
                "代码",
                "名称",
                "最新价",
                "10日涨跌幅",
                "10日主力净流入-净额",
                "10日主力净流入-净占比",
                "10日超大单净流入-净额",
                "10日超大单净流入-净占比",
                "10日大单净流入-净额",
                "10日大单净流入-净占比",
                "10日中单净流入-净额",
                "10日中单净流入-净占比",
                "10日小单净流入-净额",
                "10日小单净流入-净占比",
            ]
        ]
    return temp_df


def stock_market_fund_flow() -> pd.DataFrame:
    """
    东方财富网-数据中心-资金流向-大盘
    https://data.eastmoney.com/zjlx/dpzjlx.html
    :return: 近期大盘的资金流数据
    :rtype: pandas.DataFrame
    """
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
    }
    params = {
        "lmt": "0",
        "klt": "101",
        "secid": "1.000001",
        "secid2": "0.399001",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "_": int(time.time() * 1000),
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    content_list = data_json["data"]["klines"]
    temp_df = pd.DataFrame([item.split(",") for item in content_list])
    temp_df.columns = [
        "日期",
        "主力净流入-净额",
        "小单净流入-净额",
        "中单净流入-净额",
        "大单净流入-净额",
        "超大单净流入-净额",
        "主力净流入-净占比",
        "小单净流入-净占比",
        "中单净流入-净占比",
        "大单净流入-净占比",
        "超大单净流入-净占比",
        "上证-收盘价",
        "上证-涨跌幅",
        "深证-收盘价",
        "深证-涨跌幅",
    ]
    temp_df = temp_df[
        [
            "日期",
            "上证-收盘价",
            "上证-涨跌幅",
            "深证-收盘价",
            "深证-涨跌幅",
            "主力净流入-净额",
            "主力净流入-净占比",
            "超大单净流入-净额",
            "超大单净流入-净占比",
            "大单净流入-净额",
            "大单净流入-净占比",
            "中单净流入-净额",
            "中单净流入-净占比",
            "小单净流入-净额",
            "小单净流入-净占比",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["上证-收盘价"] = pd.to_numeric(temp_df["上证-收盘价"], errors="coerce")
    temp_df["上证-涨跌幅"] = pd.to_numeric(temp_df["上证-涨跌幅"], errors="coerce")
    temp_df["深证-收盘价"] = pd.to_numeric(temp_df["深证-收盘价"], errors="coerce")
    temp_df["深证-涨跌幅"] = pd.to_numeric(temp_df["深证-涨跌幅"], errors="coerce")
    temp_df["主力净流入-净额"] = pd.to_numeric(
        temp_df["主力净流入-净额"], errors="coerce"
    )
    temp_df["主力净流入-净占比"] = pd.to_numeric(
        temp_df["主力净流入-净占比"], errors="coerce"
    )
    temp_df["超大单净流入-净额"] = pd.to_numeric(
        temp_df["超大单净流入-净额"], errors="coerce"
    )
    temp_df["超大单净流入-净占比"] = pd.to_numeric(
        temp_df["超大单净流入-净占比"], errors="coerce"
    )
    temp_df["大单净流入-净额"] = pd.to_numeric(
        temp_df["大单净流入-净额"], errors="coerce"
    )
    temp_df["大单净流入-净占比"] = pd.to_numeric(
        temp_df["大单净流入-净占比"], errors="coerce"
    )
    temp_df["中单净流入-净额"] = pd.to_numeric(
        temp_df["中单净流入-净额"], errors="coerce"
    )
    temp_df["中单净流入-净占比"] = pd.to_numeric(
        temp_df["中单净流入-净占比"], errors="coerce"
    )
    temp_df["小单净流入-净额"] = pd.to_numeric(
        temp_df["小单净流入-净额"], errors="coerce"
    )
    temp_df["小单净流入-净占比"] = pd.to_numeric(
        temp_df["小单净流入-净占比"], errors="coerce"
    )
    return temp_df


def stock_sector_fund_flow_rank(
    indicator: str = "今日", sector_type: str = "行业资金流"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-资金流向-板块资金流-排名
    https://data.eastmoney.com/bkzj/hy.html
    :param indicator: choice of {"今日", "5日", "10日"}
    :type indicator: str
    :param sector_type: choice of {"行业资金流", "概念资金流", "地域资金流"}
    :type sector_type: str
    :return: 指定参数的资金流排名数据
    :rtype: pandas.DataFrame
    """
    sector_type_map = {"行业资金流": "2", "概念资金流": "3", "地域资金流": "1"}
    indicator_map = {
        "今日": [
            "f62",
            "1",
            "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124",
        ],
        "5日": [
            "f164",
            "5",
            "f12,f14,f2,f109,f164,f165,f166,f167,f168,f169,f170,f171,f172,f173,f257,f258,f124",
        ],
        "10日": [
            "f174",
            "10",
            "f12,f14,f2,f160,f174,f175,f176,f177,f178,f179,f180,f181,f182,f183,f260,f261,f124",
        ],
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
    }
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fltt": "2",
        "invt": "2",
        "fid0": indicator_map[indicator][0],
        "fs": f"m:90 t:{sector_type_map[sector_type]}",
        "stat": indicator_map[indicator][1],
        "fields": indicator_map[indicator][2],
        "rt": "52975239",
        "_": int(time.time() * 1000),
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    total_page = math.ceil(data_json["data"]["total"] / 100)
    temp_list = []
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pn": page,
            }
        )
        r = requests.get(url, params=params, timeout=15)
        data_json = r.json()
        inner_temp_df = pd.DataFrame(data_json["data"]["diff"])
        temp_list.append(inner_temp_df)
    temp_df = pd.concat(temp_list, ignore_index=True)

    if indicator == "今日":
        temp_df.columns = [
            "-",
            "今日涨跌幅",
            "_",
            "名称",
            "今日主力净流入-净额",
            "今日超大单净流入-净额",
            "今日超大单净流入-净占比",
            "今日大单净流入-净额",
            "今日大单净流入-净占比",
            "今日中单净流入-净额",
            "今日中单净流入-净占比",
            "今日小单净流入-净额",
            "今日小单净流入-净占比",
            "-",
            "今日主力净流入-净占比",
            "今日主力净流入最大股",
            "今日主力净流入最大股代码",
            "是否净流入",
        ]

        temp_df = temp_df[
            [
                "名称",
                "今日涨跌幅",
                "今日主力净流入-净额",
                "今日主力净流入-净占比",
                "今日超大单净流入-净额",
                "今日超大单净流入-净占比",
                "今日大单净流入-净额",
                "今日大单净流入-净占比",
                "今日中单净流入-净额",
                "今日中单净流入-净占比",
                "今日小单净流入-净额",
                "今日小单净流入-净占比",
                "今日主力净流入最大股",
            ]
        ]
        temp_df["今日主力净流入-净额"] = pd.to_numeric(
            temp_df["今日主力净流入-净额"], errors="coerce"
        )
        temp_df.sort_values(["今日主力净流入-净额"], ascending=False, inplace=True)
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.rename({"index": "序号"}, axis=1, inplace=True)
    elif indicator == "5日":
        temp_df.columns = [
            "-",
            "_",
            "名称",
            "5日涨跌幅",
            "_",
            "5日主力净流入-净额",
            "5日主力净流入-净占比",
            "5日超大单净流入-净额",
            "5日超大单净流入-净占比",
            "5日大单净流入-净额",
            "5日大单净流入-净占比",
            "5日中单净流入-净额",
            "5日中单净流入-净占比",
            "5日小单净流入-净额",
            "5日小单净流入-净占比",
            "5日主力净流入最大股",
            "_",
            "_",
        ]

        temp_df = temp_df[
            [
                "名称",
                "5日涨跌幅",
                "5日主力净流入-净额",
                "5日主力净流入-净占比",
                "5日超大单净流入-净额",
                "5日超大单净流入-净占比",
                "5日大单净流入-净额",
                "5日大单净流入-净占比",
                "5日中单净流入-净额",
                "5日中单净流入-净占比",
                "5日小单净流入-净额",
                "5日小单净流入-净占比",
                "5日主力净流入最大股",
            ]
        ]
        temp_df.sort_values(["5日主力净流入-净额"], ascending=False, inplace=True)
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.rename({"index": "序号"}, axis=1, inplace=True)
    elif indicator == "10日":
        temp_df.columns = [
            "-",
            "_",
            "名称",
            "_",
            "10日涨跌幅",
            "10日主力净流入-净额",
            "10日主力净流入-净占比",
            "10日超大单净流入-净额",
            "10日超大单净流入-净占比",
            "10日大单净流入-净额",
            "10日大单净流入-净占比",
            "10日中单净流入-净额",
            "10日中单净流入-净占比",
            "10日小单净流入-净额",
            "10日小单净流入-净占比",
            "10日主力净流入最大股",
            "_",
            "_",
        ]

        temp_df = temp_df[
            [
                "名称",
                "10日涨跌幅",
                "10日主力净流入-净额",
                "10日主力净流入-净占比",
                "10日超大单净流入-净额",
                "10日超大单净流入-净占比",
                "10日大单净流入-净额",
                "10日大单净流入-净占比",
                "10日中单净流入-净额",
                "10日中单净流入-净占比",
                "10日小单净流入-净额",
                "10日小单净流入-净占比",
                "10日主力净流入最大股",
            ]
        ]
        temp_df.sort_values(["10日主力净流入-净额"], ascending=False, inplace=True)
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.rename({"index": "序号"}, axis=1, inplace=True)
    return temp_df


@lru_cache()
def _get_stock_sector_fund_flow_summary_code() -> dict:
    """
    东方财富网-数据中心-资金流向-行业板块
    https://data.eastmoney.com/bkzj/gn.html
    :return: 行业板块与代码字典
    :rtype: dict
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "fid": "f62",
        "po": "1",
        "pz": "100",
        "pn": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
        "fs": "m:90 t:2",
        "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124,f1,f13",
    }
    temp_df = fetch_paginated_data(url, params)
    name_code_map = dict(zip(temp_df["f14"], temp_df["f12"]))
    return name_code_map


def stock_sector_fund_flow_summary(
    symbol: str = "电源设备", indicator: str = "今日"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-资金流向-行业资金流-xx行业个股资金流
    https://data.eastmoney.com/bkzj/BK1034.html
    :param symbol: 行业名称
    :type symbol: str
    :param indicator: choice of {"今日", "5日", "10日"}
    :type indicator: str
    :return: xx行业个股资金流
    :rtype: pandas.DataFrame
    """
    code_name_map = _get_stock_sector_fund_flow_summary_code()
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    if indicator == "今日":
        params = {
            "fid": "f62",
            "po": "1",
            "pz": "5000",
            "pn": "1",
            "np": "2",
            "fltt": "2",
            "invt": "2",
            "fs": f"b:{code_name_map[symbol]}",
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124,f1,f13",
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["diff"]).T
        temp_df.reset_index(inplace=True)
        temp_df["index"] = temp_df["index"].astype(int) + 1
        temp_df.rename(
            columns={
                "index": "序号",
                "f12": "代码",
                "f14": "名称",
                "f2": "最新价",
                "f3": "今天涨跌幅",
                "f62": "今日主力净流入-净额",
                "f184": "今日主力净流入-净占比",
                "f66": "今日超大单净流入-净额",
                "f69": "今日超大单净流入-净占比",
                "f72": "今日大单净流入-净额",
                "f75": "今日大单净流入-净占比",
                "f78": "今日中单净流入-净额",
                "f81": "今日中单净流入-净占比",
                "f84": "今日小单净流入-净额",
                "f87": "今日小单净流入-净占比",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "序号",
                "代码",
                "名称",
                "最新价",
                "今天涨跌幅",
                "今日主力净流入-净额",
                "今日主力净流入-净占比",
                "今日超大单净流入-净额",
                "今日超大单净流入-净占比",
                "今日大单净流入-净额",
                "今日大单净流入-净占比",
                "今日中单净流入-净额",
                "今日中单净流入-净占比",
                "今日小单净流入-净额",
                "今日小单净流入-净占比",
            ]
        ]
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["今天涨跌幅"] = pd.to_numeric(temp_df["今天涨跌幅"], errors="coerce")
        temp_df["今日主力净流入-净额"] = pd.to_numeric(
            temp_df["今日主力净流入-净额"], errors="coerce"
        )
        temp_df["今日主力净流入-净占比"] = pd.to_numeric(
            temp_df["今日主力净流入-净占比"], errors="coerce"
        )
        temp_df["今日超大单净流入-净额"] = pd.to_numeric(
            temp_df["今日超大单净流入-净额"], errors="coerce"
        )
        temp_df["今日超大单净流入-净占比"] = pd.to_numeric(
            temp_df["今日超大单净流入-净占比"], errors="coerce"
        )
        temp_df["今日大单净流入-净额"] = pd.to_numeric(
            temp_df["今日大单净流入-净额"], errors="coerce"
        )
        temp_df["今日大单净流入-净占比"] = pd.to_numeric(
            temp_df["今日大单净流入-净占比"], errors="coerce"
        )
        temp_df["今日中单净流入-净额"] = pd.to_numeric(
            temp_df["今日中单净流入-净额"], errors="coerce"
        )
        temp_df["今日中单净流入-净占比"] = pd.to_numeric(
            temp_df["今日中单净流入-净占比"], errors="coerce"
        )
        temp_df["今日小单净流入-净额"] = pd.to_numeric(
            temp_df["今日小单净流入-净额"], errors="coerce"
        )
        temp_df["今日小单净流入-净占比"] = pd.to_numeric(
            temp_df["今日小单净流入-净占比"], errors="coerce"
        )
        return temp_df
    if indicator == "5日":
        params = {
            "fid": "f164",
            "po": "1",
            "pz": "50000",
            "pn": "1",
            "np": "2",
            "fltt": "2",
            "invt": "2",
            "fs": f"b:{code_name_map[symbol]}",
            "fields": "f12,f14,f2,f109,f164,f165,f166,f167,f168,f169,f170,f171,f172,f173,f257,f258,f124,f1,f13",
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["diff"]).T
        temp_df.reset_index(inplace=True)
        temp_df["index"] = temp_df["index"].astype(int) + 1
        temp_df.rename(
            columns={
                "index": "序号",
                "f12": "代码",
                "f14": "名称",
                "f2": "最新价",
                "f109": "5日涨跌幅",
                "f164": "5日主力净流入-净额",
                "f165": "5日主力净流入-净占比",
                "f166": "5日超大单净流入-净额",
                "f167": "5日超大单净流入-净占比",
                "f168": "5日大单净流入-净额",
                "f169": "5日大单净流入-净占比",
                "f170": "5日中单净流入-净额",
                "f171": "5日中单净流入-净占比",
                "f172": "5日小单净流入-净额",
                "f173": "5日小单净流入-净占比",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "序号",
                "代码",
                "名称",
                "最新价",
                "5日涨跌幅",
                "5日主力净流入-净额",
                "5日主力净流入-净占比",
                "5日超大单净流入-净额",
                "5日超大单净流入-净占比",
                "5日大单净流入-净额",
                "5日大单净流入-净占比",
                "5日中单净流入-净额",
                "5日中单净流入-净占比",
                "5日小单净流入-净额",
                "5日小单净流入-净占比",
            ]
        ]
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["5日涨跌幅"] = pd.to_numeric(temp_df["5日涨跌幅"], errors="coerce")
        temp_df["5日主力净流入-净额"] = pd.to_numeric(
            temp_df["5日主力净流入-净额"], errors="coerce"
        )
        temp_df["5日主力净流入-净占比"] = pd.to_numeric(
            temp_df["5日主力净流入-净占比"], errors="coerce"
        )
        temp_df["5日超大单净流入-净额"] = pd.to_numeric(
            temp_df["5日超大单净流入-净额"], errors="coerce"
        )
        temp_df["5日超大单净流入-净占比"] = pd.to_numeric(
            temp_df["5日超大单净流入-净占比"], errors="coerce"
        )
        temp_df["5日大单净流入-净额"] = pd.to_numeric(
            temp_df["5日大单净流入-净额"], errors="coerce"
        )
        temp_df["5日大单净流入-净占比"] = pd.to_numeric(
            temp_df["5日大单净流入-净占比"], errors="coerce"
        )
        temp_df["5日中单净流入-净额"] = pd.to_numeric(
            temp_df["5日中单净流入-净额"], errors="coerce"
        )
        temp_df["5日中单净流入-净占比"] = pd.to_numeric(
            temp_df["5日中单净流入-净占比"], errors="coerce"
        )
        temp_df["5日小单净流入-净额"] = pd.to_numeric(
            temp_df["5日小单净流入-净额"], errors="coerce"
        )
        temp_df["5日小单净流入-净占比"] = pd.to_numeric(
            temp_df["5日小单净流入-净占比"], errors="coerce"
        )
        return temp_df
    if indicator == "10日":
        params = {
            "fid": "f174",
            "po": "1",
            "pz": "50000",
            "pn": "1",
            "np": "2",
            "fltt": "2",
            "invt": "2",
            "fs": f"b:{code_name_map[symbol]}",
            "fields": "f12,f14,f2,f160,f174,f175,f176,f177,f178,f179,f180,f181,f182,f183,f260,f261,f124,f1,f13",
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["diff"]).T
        temp_df.reset_index(inplace=True)
        temp_df["index"] = temp_df["index"].astype(int) + 1
        temp_df.rename(
            columns={
                "index": "序号",
                "f12": "代码",
                "f14": "名称",
                "f2": "最新价",
                "f160": "10日涨跌幅",
                "f174": "10日主力净流入-净额",
                "f175": "10日主力净流入-净占比",
                "f176": "10日超大单净流入-净额",
                "f177": "10日超大单净流入-净占比",
                "f178": "10日大单净流入-净额",
                "f179": "10日大单净流入-净占比",
                "f180": "10日中单净流入-净额",
                "f181": "10日中单净流入-净占比",
                "f182": "10日小单净流入-净额",
                "f183": "10日小单净流入-净占比",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "序号",
                "代码",
                "名称",
                "最新价",
                "10日涨跌幅",
                "10日主力净流入-净额",
                "10日主力净流入-净占比",
                "10日超大单净流入-净额",
                "10日超大单净流入-净占比",
                "10日大单净流入-净额",
                "10日大单净流入-净占比",
                "10日中单净流入-净额",
                "10日中单净流入-净占比",
                "10日小单净流入-净额",
                "10日小单净流入-净占比",
            ]
        ]
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["10日涨跌幅"] = pd.to_numeric(temp_df["10日涨跌幅"], errors="coerce")
        temp_df["10日主力净流入-净额"] = pd.to_numeric(
            temp_df["10日主力净流入-净额"], errors="coerce"
        )
        temp_df["10日主力净流入-净占比"] = pd.to_numeric(
            temp_df["10日主力净流入-净占比"], errors="coerce"
        )
        temp_df["10日超大单净流入-净额"] = pd.to_numeric(
            temp_df["10日超大单净流入-净额"], errors="coerce"
        )
        temp_df["10日超大单净流入-净占比"] = pd.to_numeric(
            temp_df["10日超大单净流入-净占比"], errors="coerce"
        )
        temp_df["10日大单净流入-净额"] = pd.to_numeric(
            temp_df["10日大单净流入-净额"], errors="coerce"
        )
        temp_df["10日大单净流入-净占比"] = pd.to_numeric(
            temp_df["10日大单净流入-净占比"], errors="coerce"
        )
        temp_df["10日中单净流入-净额"] = pd.to_numeric(
            temp_df["10日中单净流入-净额"], errors="coerce"
        )
        temp_df["10日中单净流入-净占比"] = pd.to_numeric(
            temp_df["10日中单净流入-净占比"], errors="coerce"
        )
        temp_df["10日小单净流入-净额"] = pd.to_numeric(
            temp_df["10日小单净流入-净额"], errors="coerce"
        )
        temp_df["10日小单净流入-净占比"] = pd.to_numeric(
            temp_df["10日小单净流入-净占比"], errors="coerce"
        )
        return temp_df
    else:
        return pd.DataFrame()


def stock_sector_fund_flow_hist(symbol: str = "汽车服务") -> pd.DataFrame:
    """
    东方财富网-数据中心-资金流向-行业资金流-行业历史资金流
    https://data.eastmoney.com/bkzj/BK1034.html
    :param symbol: 行业名称
    :type symbol: str
    :return: xx行业个股资金流
    :rtype: pandas.DataFrame
    """
    code_name_map = _get_stock_sector_fund_flow_summary_code()
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "lmt": "0",
        "klt": "101",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "secid": f"90.{code_name_map[symbol]}",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    temp_df.columns = [
        "日期",
        "主力净流入-净额",
        "小单净流入-净额",
        "中单净流入-净额",
        "大单净流入-净额",
        "超大单净流入-净额",
        "主力净流入-净占比",
        "小单净流入-净占比",
        "中单净流入-净占比",
        "大单净流入-净占比",
        "超大单净流入-净占比",
        "-",
        "-",
        "-",
        "-",
    ]
    temp_df = temp_df[
        [
            "日期",
            "主力净流入-净额",
            "主力净流入-净占比",
            "超大单净流入-净额",
            "超大单净流入-净占比",
            "大单净流入-净额",
            "大单净流入-净占比",
            "中单净流入-净额",
            "中单净流入-净占比",
            "小单净流入-净额",
            "小单净流入-净占比",
        ]
    ]
    temp_df["主力净流入-净额"] = pd.to_numeric(
        temp_df["主力净流入-净额"], errors="coerce"
    )
    temp_df["主力净流入-净占比"] = pd.to_numeric(
        temp_df["主力净流入-净占比"], errors="coerce"
    )
    temp_df["超大单净流入-净额"] = pd.to_numeric(
        temp_df["超大单净流入-净额"], errors="coerce"
    )
    temp_df["超大单净流入-净占比"] = pd.to_numeric(
        temp_df["超大单净流入-净占比"], errors="coerce"
    )
    temp_df["大单净流入-净额"] = pd.to_numeric(
        temp_df["大单净流入-净额"], errors="coerce"
    )
    temp_df["大单净流入-净占比"] = pd.to_numeric(
        temp_df["大单净流入-净占比"], errors="coerce"
    )
    temp_df["中单净流入-净额"] = pd.to_numeric(
        temp_df["中单净流入-净额"], errors="coerce"
    )
    temp_df["中单净流入-净占比"] = pd.to_numeric(
        temp_df["中单净流入-净占比"], errors="coerce"
    )
    temp_df["小单净流入-净额"] = pd.to_numeric(
        temp_df["小单净流入-净额"], errors="coerce"
    )
    temp_df["小单净流入-净占比"] = pd.to_numeric(
        temp_df["小单净流入-净占比"], errors="coerce"
    )
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    return temp_df


@lru_cache()
def _get_stock_concept_fund_flow_summary_code() -> dict:
    """
    东方财富网-数据中心-资金流向-概念资金流
    https://data.eastmoney.com/bkzj/gn.html
    :return: 概念与代码字典
    :rtype: dict
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "fields": "f3,f12,f13,f14,f62",
        "fid": "f62",
        "fs": "m:90+t:3",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "_": int(time.time() * 1000),
    }
    temp_df = fetch_paginated_data(url, params)
    name_code_map = dict(zip(temp_df["f14"], temp_df["f12"]))
    return name_code_map


def stock_concept_fund_flow_hist(symbol: str = "数据要素") -> pd.DataFrame:
    """
    东方财富网-数据中心-资金流向-概念资金流-概念历史资金流
    https://data.eastmoney.com/bkzj/BK0574.html
    :param symbol: 概念名称
    :type symbol: str
    :return: 概念历史资金流
    :rtype: pandas.DataFrame
    """
    code_name_map = _get_stock_concept_fund_flow_summary_code()
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "lmt": "0",
        "klt": "101",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "secid": f"90.{code_name_map[symbol]}",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    temp_df.columns = [
        "日期",
        "主力净流入-净额",
        "小单净流入-净额",
        "中单净流入-净额",
        "大单净流入-净额",
        "超大单净流入-净额",
        "主力净流入-净占比",
        "小单净流入-净占比",
        "中单净流入-净占比",
        "大单净流入-净占比",
        "超大单净流入-净占比",
        "-",
        "-",
        "-",
        "-",
    ]
    temp_df = temp_df[
        [
            "日期",
            "主力净流入-净额",
            "主力净流入-净占比",
            "超大单净流入-净额",
            "超大单净流入-净占比",
            "大单净流入-净额",
            "大单净流入-净占比",
            "中单净流入-净额",
            "中单净流入-净占比",
            "小单净流入-净额",
            "小单净流入-净占比",
        ]
    ]
    temp_df["主力净流入-净额"] = pd.to_numeric(
        temp_df["主力净流入-净额"], errors="coerce"
    )
    temp_df["主力净流入-净占比"] = pd.to_numeric(
        temp_df["主力净流入-净占比"], errors="coerce"
    )
    temp_df["超大单净流入-净额"] = pd.to_numeric(
        temp_df["超大单净流入-净额"], errors="coerce"
    )
    temp_df["超大单净流入-净占比"] = pd.to_numeric(
        temp_df["超大单净流入-净占比"], errors="coerce"
    )
    temp_df["大单净流入-净额"] = pd.to_numeric(
        temp_df["大单净流入-净额"], errors="coerce"
    )
    temp_df["大单净流入-净占比"] = pd.to_numeric(
        temp_df["大单净流入-净占比"], errors="coerce"
    )
    temp_df["中单净流入-净额"] = pd.to_numeric(
        temp_df["中单净流入-净额"], errors="coerce"
    )
    temp_df["中单净流入-净占比"] = pd.to_numeric(
        temp_df["中单净流入-净占比"], errors="coerce"
    )
    temp_df["小单净流入-净额"] = pd.to_numeric(
        temp_df["小单净流入-净额"], errors="coerce"
    )
    temp_df["小单净流入-净占比"] = pd.to_numeric(
        temp_df["小单净流入-净占比"], errors="coerce"
    )
    temp_df["日期"] = pd.to_datetime(temp_df["日期"]).dt.date
    return temp_df


def stock_main_fund_flow(symbol: str = "全部股票") -> pd.DataFrame:
    """
    东方财富网-数据中心-资金流向-主力净流入排名
    https://data.eastmoney.com/zjlx/list.html
    :param symbol: 全部股票; choice of {"全部股票", "沪深A股", "沪市A股", "科创板", "深市A股", "创业板", "沪市B股", "深市B股"}
    :type symbol: str
    :return: 主力净流入排名
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "全部股票": "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2",
        "沪深A股": "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2",
        "沪市A股": "m:1+t:2+f:!2,m:1+t:23+f:!2",
        "科创板": "m:1+t:23+f:!2",
        "深市A股": "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2",
        "创业板": "m:0+t:80+f:!2",
        "沪市B股": "m:1+t:3+f:!2",
        "深市B股": "m:0+t:7+f:!2",
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "fid": "f184",
        "po": "1",
        "pz": "100",
        "pn": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fields": "f2,f3,f12,f13,f14,f62,f184,f225,f165,f263,f109,f175,f264,f160,f100,f124,f265,f1",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fs": symbol_map[symbol],
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.rename(
        columns={
            "index": "序号",
            "f12": "代码",
            "f14": "名称",
            "f2": "最新价",
            "f184": "今日排行榜-主力净占比",
            "f225": "今日排行榜-今日排名",
            "f3": "今日排行榜-今日涨跌",
            "f165": "5日排行榜-主力净占比",
            "f263": "5日排行榜-5日排名",
            "f109": "5日排行榜-5日涨跌",
            "f175": "10日排行榜-主力净占比",
            "f264": "10日排行榜-10日排名",
            "f160": "10日排行榜-10日涨跌",
            "f100": "所属板块",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "代码",
            "名称",
            "最新价",
            "今日排行榜-主力净占比",
            "今日排行榜-今日排名",
            "今日排行榜-今日涨跌",
            "5日排行榜-主力净占比",
            "5日排行榜-5日排名",
            "5日排行榜-5日涨跌",
            "10日排行榜-主力净占比",
            "10日排行榜-10日排名",
            "10日排行榜-10日涨跌",
            "所属板块",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["今日排行榜-主力净占比"] = pd.to_numeric(
        temp_df["今日排行榜-主力净占比"], errors="coerce"
    )
    temp_df["今日排行榜-今日排名"] = pd.to_numeric(
        temp_df["今日排行榜-今日排名"], errors="coerce"
    )
    temp_df["今日排行榜-今日涨跌"] = pd.to_numeric(
        temp_df["今日排行榜-今日涨跌"], errors="coerce"
    )
    temp_df["5日排行榜-主力净占比"] = pd.to_numeric(
        temp_df["5日排行榜-主力净占比"], errors="coerce"
    )
    temp_df["5日排行榜-5日排名"] = pd.to_numeric(
        temp_df["5日排行榜-5日排名"], errors="coerce"
    )
    temp_df["5日排行榜-5日涨跌"] = pd.to_numeric(
        temp_df["5日排行榜-5日涨跌"], errors="coerce"
    )
    temp_df["10日排行榜-主力净占比"] = pd.to_numeric(
        temp_df["10日排行榜-主力净占比"], errors="coerce"
    )
    temp_df["10日排行榜-10日排名"] = pd.to_numeric(
        temp_df["10日排行榜-10日排名"], errors="coerce"
    )
    temp_df["10日排行榜-10日涨跌"] = pd.to_numeric(
        temp_df["10日排行榜-10日涨跌"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    stock_individual_fund_flow_df = stock_individual_fund_flow(
        stock="600094", market="sh"
    )
    print(stock_individual_fund_flow_df)

    stock_individual_fund_flow_rank_df = stock_individual_fund_flow_rank(
        indicator="今日"
    )
    print(stock_individual_fund_flow_rank_df)

    stock_individual_fund_flow_rank_df = stock_individual_fund_flow_rank(
        indicator="3日"
    )
    print(stock_individual_fund_flow_rank_df)

    stock_individual_fund_flow_rank_df = stock_individual_fund_flow_rank(
        indicator="5日"
    )
    print(stock_individual_fund_flow_rank_df)

    stock_individual_fund_flow_rank_df = stock_individual_fund_flow_rank(
        indicator="10日"
    )
    print(stock_individual_fund_flow_rank_df)

    stock_market_fund_flow_df = stock_market_fund_flow()
    print(stock_market_fund_flow_df)

    stock_sector_fund_flow_rank_df = stock_sector_fund_flow_rank(
        indicator="今日", sector_type="地域资金流"
    )
    print(stock_sector_fund_flow_rank_df)

    stock_sector_fund_flow_rank_df = stock_sector_fund_flow_rank(
        indicator="今日", sector_type="行业资金流"
    )
    print(stock_sector_fund_flow_rank_df)

    stock_sector_fund_flow_rank_df = stock_sector_fund_flow_rank(
        indicator="今日", sector_type="概念资金流"
    )
    print(stock_sector_fund_flow_rank_df)

    stock_sector_fund_flow_summary_df = stock_sector_fund_flow_summary(
        symbol="文化传媒", indicator="今日"
    )
    print(stock_sector_fund_flow_summary_df)

    stock_sector_fund_flow_hist_df = stock_sector_fund_flow_hist(symbol="汽车服务")
    print(stock_sector_fund_flow_hist_df)

    stock_concept_fund_flow_hist_df = stock_concept_fund_flow_hist(symbol="半导体概念")
    print(stock_concept_fund_flow_hist_df)

    stock_main_fund_flow_df = stock_main_fund_flow(symbol="全部股票")
    print(stock_main_fund_flow_df)
