#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/6/28 14:57
Desc: 中国外汇交易中心暨全国银行间同业拆借中心-市场数据-市场行情-外汇市场行情
人民币外汇即期报价: fx_spot_quote
人民币外汇远掉报价: fx_swap_quote
外币对即期报价: fx_pair_quote
"""

import time

import pandas as pd
import requests

from akshare.fx.cons import (
    SHORT_HEADERS,
    FX_SPOT_URL,
    FX_SWAP_URL,
    FX_PAIR_URL,
)


def fx_spot_quote() -> pd.DataFrame:
    """
    中国外汇交易中心暨全国银行间同业拆借中心-市场数据-市场行情-外汇市场行情-人民币外汇即期报价
    http://www.chinamoney.com.cn/chinese/mkdatapfx/
    :return: 人民币外汇即期报价
    :rtype: pandas.DataFrame
    """
    payload = {"t": str(int(round(time.time() * 1000)))}
    res = requests.post(FX_SPOT_URL, data=payload, headers=SHORT_HEADERS)
    temp_df = pd.DataFrame(res.json()["records"])
    temp_df = temp_df[["ccyPair", "bidPrc", "askPrc", "midprice", "time"]]
    temp_df.columns = [
        "货币对",
        "买报价",
        "卖报价",
        "-",
        "-",
    ]
    temp_df = temp_df[["货币对", "买报价", "卖报价"]]
    temp_df["买报价"] = pd.to_numeric(temp_df["买报价"], errors="coerce")
    temp_df["卖报价"] = pd.to_numeric(temp_df["卖报价"], errors="coerce")
    return temp_df


def fx_swap_quote() -> pd.DataFrame:
    """
    中国外汇交易中心暨全国银行间同业拆借中心-市场数据-市场行情-债券市场行情-人民币外汇远掉报价
    https://www.chinamoney.com.cn/chinese/index.html
    :return: 人民币外汇远掉报价
    :return: pandas.DataFrame
    """
    payload = {"t": str(int(round(time.time() * 1000)))}
    res = requests.post(FX_SWAP_URL, data=payload, headers=SHORT_HEADERS)
    temp_df = pd.DataFrame(res.json()["records"])
    temp_df = temp_df[
        [
            "ccyPair",
            "label_1W",
            "label_1M",
            "label_3M",
            "label_6M",
            "label_9M",
            "label_1Y",
        ]
    ]
    temp_df.columns = [
        "货币对",
        "1周",
        "1月",
        "3月",
        "6月",
        "9月",
        "1年",
    ]
    return temp_df


def fx_pair_quote() -> pd.DataFrame:
    """
    中国外汇交易中心暨全国银行间同业拆借中心-市场数据-市场行情-债券市场行情-外币对即期报价
    http://www.chinamoney.com.cn/chinese/mkdatapfx/
    :return: 外币对即期报价
    :return: pandas.DataFrame
    """
    payload = {"t": str(int(round(time.time() * 1000)))}
    res = requests.post(FX_PAIR_URL, data=payload, headers=SHORT_HEADERS)
    temp_df = pd.DataFrame(res.json()["records"])
    temp_df = temp_df[["ccyPair", "bidPrc", "askPrc", "midprice", "time"]]
    temp_df.columns = [
        "货币对",
        "买报价",
        "卖报价",
        "-",
        "-",
    ]
    temp_df = temp_df[["货币对", "买报价", "卖报价"]]
    temp_df["买报价"] = pd.to_numeric(temp_df["买报价"], errors="coerce")
    temp_df["卖报价"] = pd.to_numeric(temp_df["卖报价"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    fx_spot_quote_df = fx_spot_quote()
    print(fx_spot_quote_df)

    fx_swap_quote_df = fx_swap_quote()
    print(fx_swap_quote_df)

    fx_pair_quote_df = fx_pair_quote()
    print(fx_pair_quote_df)
