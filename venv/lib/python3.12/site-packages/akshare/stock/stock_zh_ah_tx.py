#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/2/26 15:10
Desc: 腾讯财经-A+H股数据, 实时行情数据和历史行情数据(后复权)
https://stockapp.finance.qq.com/mstats/#mod=list&id=hk_ah&module=HK&type=AH&sort=3&page=3&max=20
"""

import random

import pandas as pd
import requests

from akshare.stock.cons import (
    hk_url,
    hk_headers,
    hk_payload,
    hk_stock_headers,
    hk_stock_payload,
)
from akshare.utils import demjson
from akshare.utils.tqdm import get_tqdm


def _get_zh_stock_ah_page_count() -> int:
    """
    腾讯财经-港股-AH-总页数
    https://stockapp.finance.qq.com/mstats/#mod=list&id=hk_ah&module=HK&type=AH&sort=3&page=3&max=20
    :return: 总页数
    :rtype: int
    """
    hk_payload_copy = hk_payload.copy()
    hk_payload_copy.update({"reqPage": 1})
    r = requests.get(hk_url, params=hk_payload_copy, headers=hk_headers)
    data_json = demjson.decode(r.text[r.text.find("{") : r.text.rfind("}") + 1])
    page_count = data_json["data"]["page_count"]
    return page_count


def stock_zh_ah_spot() -> pd.DataFrame:
    """
    腾讯财经-港股-AH-实时行情
    https://stockapp.finance.qq.com/mstats/#mod=list&id=hk_ah&module=HK&type=AH&sort=3&page=3&max=20
    :return: 腾讯财经-港股-AH-实时行情
    :rtype: pandas.DataFrame
    """
    page_count = _get_zh_stock_ah_page_count()
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for i in tqdm(range(0, page_count), leave=False):
        hk_payload.update({"reqPage": i})
        r = requests.get(hk_url, params=hk_payload, headers=hk_headers)
        data_json = demjson.decode(r.text[r.text.find("{") : r.text.rfind("}") + 1])
        big_df = pd.concat(
            objs=[
                big_df,
                pd.DataFrame(data_json["data"]["page_data"])
                .iloc[:, 0]
                .str.split("~", expand=True),
            ],
            ignore_index=True,
        )
    big_df.columns = [
        "代码",
        "名称",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "买入",
        "卖出",
        "成交量",
        "成交额",
        "今开",
        "昨收",
        "最高",
        "最低",
        "-",
    ]
    big_df = big_df[
        [
            "代码",
            "名称",
            "最新价",
            "涨跌幅",
            "涨跌额",
            "买入",
            "卖出",
            "成交量",
            "成交额",
            "今开",
            "昨收",
            "最高",
            "最低",
        ]
    ]
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["涨跌额"] = pd.to_numeric(big_df["涨跌额"], errors="coerce")
    big_df["买入"] = pd.to_numeric(big_df["买入"], errors="coerce")
    big_df["卖出"] = pd.to_numeric(big_df["卖出"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["成交额"] = pd.to_numeric(big_df["成交额"], errors="coerce")
    big_df["今开"] = pd.to_numeric(big_df["今开"], errors="coerce")
    big_df["昨收"] = pd.to_numeric(big_df["昨收"], errors="coerce")
    big_df["最高"] = pd.to_numeric(big_df["最高"], errors="coerce")
    big_df["最低"] = pd.to_numeric(big_df["最低"], errors="coerce")
    return big_df


def stock_zh_ah_name() -> pd.DataFrame:
    """
    腾讯财经-港股-AH-股票名称
    https://stockapp.finance.qq.com/mstats/#mod=list&id=hk_ah&module=HK&type=AH
    :return: 股票代码和股票名称的字典
    :rtype: pandas.DataFrame
    """
    big_df = pd.DataFrame()
    page_count = _get_zh_stock_ah_page_count()
    tqdm = get_tqdm()
    for i in tqdm(range(0, page_count), leave=False):
        hk_payload.update({"reqPage": i})
        r = requests.get(hk_url, params=hk_payload, headers=hk_headers)
        data_json = demjson.decode(r.text[r.text.find("{") : r.text.rfind("}") + 1])
        big_df = pd.concat(
            objs=[
                big_df,
                pd.DataFrame(data_json["data"]["page_data"])
                .iloc[:, 0]
                .str.split("~", expand=True),
            ],
            ignore_index=True,
        ).iloc[:, :-1]
    big_df.columns = [
        "代码",
        "名称",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "买入",
        "卖出",
        "成交量",
        "成交额",
        "今开",
        "昨收",
        "最高",
        "最低",
    ]
    big_df = big_df[
        [
            "代码",
            "名称",
        ]
    ]
    return big_df


def stock_zh_ah_daily(
    symbol: str = "02318",
    start_year: str = "2000",
    end_year: str = "2019",
    adjust: str = "",
) -> pd.DataFrame:
    """
    腾讯财经-港股-AH-股票历史行情
    https://gu.qq.com/hk01033/gp
    :param symbol: 股票代码
    :type symbol: str
    :param start_year: 开始年份; e.g., “2000”
    :type start_year: str
    :param end_year: 结束年份; e.g., “2019”
    :type end_year: str
    :param adjust: 'qfq': 前复权, 'hfq': 后复权
    :type adjust: str
    :return: 指定股票在指定年份的日频率历史行情数据
    :rtype: pandas.DataFrame
    """
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for year in tqdm(range(int(start_year), int(end_year)), leave=False):
        # year = "2003"
        hk_stock_payload_copy = hk_stock_payload.copy()
        hk_stock_payload_copy.update({"_var": f"kline_day{adjust}{year}"})
        if adjust == "":
            hk_stock_payload_copy.update(
                {"param": f"hk{symbol},day,{year}-01-01,{int(year) + 1}-12-31,640,"}
            )
        else:
            hk_stock_payload_copy.update(
                {
                    "param": f"hk{symbol},day,{year}-01-01,{int(year) + 1}-12-31,640,{adjust}"
                }
            )
        hk_stock_payload_copy.update({"r": str(random.random())})
        if adjust == "":
            headers = {
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Host": "web.ifzq.gtimg.cn",
                "Pragma": "no-cache",
                "Referer": "http://gu.qq.com/hk01033/gp",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36",
            }
            r = requests.get(
                url="http://web.ifzq.gtimg.cn/appstock/app/kline/kline",
                params=hk_stock_payload_copy,
                headers=headers,
            )
        else:
            r = requests.get(
                url="https://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get",
                params=hk_stock_payload_copy,
                headers=hk_stock_headers,
            )
        data_json = demjson.decode(r.text[r.text.find("{") : r.text.rfind("}") + 1])
        try:
            if adjust == "":
                temp_df = pd.DataFrame(data_json["data"][f"hk{symbol}"]["day"])
            else:
                temp_df = pd.DataFrame(data_json["data"][f"hk{symbol}"][f"{adjust}day"])
        except:  # noqa
            continue
        if adjust != "" and not temp_df.empty:
            temp_df.columns = [
                "日期",
                "开盘",
                "收盘",
                "最高",
                "最低",
                "成交量",
                "_",
                "_",
                "_",
            ]
            temp_df = temp_df[["日期", "开盘", "收盘", "最高", "最低", "成交量"]]
        elif not temp_df.empty:
            try:
                temp_df.columns = [
                    "日期",
                    "开盘",
                    "收盘",
                    "最高",
                    "最低",
                    "成交量",
                    "_",
                ]
            except:  # noqa
                temp_df.columns = ["日期", "开盘", "收盘", "最高", "最低", "成交量"]
            temp_df = temp_df[["日期", "开盘", "收盘", "最高", "最低", "成交量"]]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["开盘"] = pd.to_numeric(big_df["开盘"], errors="coerce")
    big_df["收盘"] = pd.to_numeric(big_df["收盘"], errors="coerce")
    big_df["最高"] = pd.to_numeric(big_df["最高"], errors="coerce")
    big_df["最低"] = pd.to_numeric(big_df["最低"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    return big_df


if __name__ == "__main__":
    stock_zh_ah_spot_df = stock_zh_ah_spot()
    print(stock_zh_ah_spot_df)

    stock_zh_ah_name_df = stock_zh_ah_name()
    print(stock_zh_ah_name_df)

    stock_zh_ah_daily_df = stock_zh_ah_daily(
        symbol="02318", start_year="2022", end_year="2024", adjust=""
    )
    print(stock_zh_ah_daily_df)
