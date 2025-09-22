#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/7/6 19:28
Desc: 新浪财经-科创板-实时行情数据和历史行情数据(包含前复权和后复权因子)
"""

import datetime
import re

from akshare.utils import demjson
import pandas as pd
import requests
from tqdm import tqdm

from akshare.stock.cons import (
    zh_sina_kcb_stock_payload,
    zh_sina_kcb_stock_url,
    zh_sina_kcb_stock_count_url,
    zh_sina_kcb_stock_hist_url,
    zh_sina_kcb_stock_hfq_url,
    zh_sina_kcb_stock_qfq_url,
    zh_sina_kcb_stock_amount_url,
)


def get_zh_kcb_page_count() -> int:
    """
    所有股票的总页数
    https://vip.stock.finance.sina.com.cn/mkt/#hs_a
    :return: 所有股票的总页数
    :rtype: int
    """
    res = requests.get(zh_sina_kcb_stock_count_url)
    page_count = int(re.findall(re.compile(r"\d+"), res.text)[0]) / 80
    if isinstance(page_count, int):
        return page_count
    else:
        return int(page_count) + 1


def stock_zh_kcb_spot() -> pd.DataFrame:
    """
    新浪财经-科创板实时行情数据, 大量抓取容易封IP
    https://vip.stock.finance.sina.com.cn/mkt/#kcb
    :return: 科创板实时行情数据
    :rtype: pandas.DataFrame
    """
    big_df = pd.DataFrame()
    page_count = get_zh_kcb_page_count()
    zh_sina_stock_payload_copy = zh_sina_kcb_stock_payload.copy()
    for page in tqdm(range(1, page_count + 1), leave=False):
        zh_sina_stock_payload_copy.update({"page": page})
        zh_sina_stock_payload_copy.update({"_s_r_a": "page"})
        res = requests.get(zh_sina_kcb_stock_url, params=zh_sina_stock_payload_copy)
        data_json = demjson.decode(res.text)
        big_df = pd.concat([big_df, pd.DataFrame(data_json)], ignore_index=True)
    big_df.columns = [
        "代码",
        "-",
        "名称",
        "最新价",
        "涨跌额",
        "涨跌幅",
        "买入",
        "卖出",
        "昨收",
        "今开",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "时点",
        "市盈率",
        "市净率",
        "流通市值",
        "总市值",
        "换手率",
    ]
    big_df = big_df[
        [
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "买入",
            "卖出",
            "昨收",
            "今开",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "时点",
            "市盈率",
            "市净率",
            "流通市值",
            "总市值",
            "换手率",
        ]
    ]

    big_df["最新价"] = pd.to_numeric(big_df["最新价"])
    big_df["涨跌额"] = pd.to_numeric(big_df["涨跌额"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["买入"] = pd.to_numeric(big_df["买入"])
    big_df["卖出"] = pd.to_numeric(big_df["卖出"])
    big_df["昨收"] = pd.to_numeric(big_df["昨收"])
    big_df["今开"] = pd.to_numeric(big_df["今开"])
    big_df["最高"] = pd.to_numeric(big_df["最高"])
    big_df["最低"] = pd.to_numeric(big_df["最低"])
    big_df["成交量"] = pd.to_numeric(big_df["成交量"])
    big_df["成交额"] = pd.to_numeric(big_df["成交额"])
    big_df["市盈率"] = pd.to_numeric(big_df["市盈率"])
    big_df["市净率"] = pd.to_numeric(big_df["市净率"])
    big_df["流通市值"] = pd.to_numeric(big_df["流通市值"])
    big_df["总市值"] = pd.to_numeric(big_df["总市值"])
    big_df["换手率"] = pd.to_numeric(big_df["换手率"])
    return big_df


def stock_zh_kcb_daily(symbol: str = "sh688399", adjust: str = "") -> pd.DataFrame:
    """
    新浪财经-科创板股票的历史行情数据, 大量抓取容易封IP
    https://finance.sina.com.cn/realstock/company/sh688005/nc.shtml
    :param symbol: 股票代码; 带市场标识的股票代码
    :type symbol: str
    :param adjust: 默认不复权的数据; qfq: 返回前复权后的数据; hfq: 返回后复权后的数据; hfq-factor: 返回后复权因子; qfq-factor: 返回前复权因子
    :type adjust: str
    :return: 科创板股票的历史行情数据
    :rtype: pandas.DataFrame
    """
    res = requests.get(
        zh_sina_kcb_stock_hist_url.format(
            symbol, datetime.datetime.now().strftime("%Y_%m_%d"), symbol
        )
    )
    data_json = demjson.decode(res.text[res.text.find("[") : res.text.rfind("]") + 1])
    data_df = pd.DataFrame(data_json)
    data_df.index = pd.to_datetime(data_df["d"])
    data_df.index.name = "date"
    del data_df["d"]

    r = requests.get(zh_sina_kcb_stock_amount_url.format(symbol, symbol))
    amount_data_json = demjson.decode(r.text[r.text.find("[") : r.text.rfind("]") + 1])
    amount_data_df = pd.DataFrame(amount_data_json)
    amount_data_df.index = pd.to_datetime(amount_data_df.date)
    del amount_data_df["date"]
    temp_df = pd.merge(
        data_df, amount_data_df, left_index=True, right_index=True, how="left"
    )
    try:
        # try for pandas >= 2.1.0
        temp_df.ffill(inplace=True)
    except Exception:
        try:
            # try for pandas < 2.1.0
            temp_df.fillna(method="ffill", inplace=True)
        except Exception as e:
            print("Error:", e)
    temp_df = temp_df.astype(float)
    temp_df["amount"] = temp_df["amount"] * 10000
    temp_df["turnover"] = temp_df["v"] / temp_df["amount"]
    temp_df.columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "after_volume",
        "after_amount",
        "outstanding_share",
        "turnover",
    ]

    if not adjust:
        temp_df.reset_index(inplace=True)
        temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
        return temp_df

    if adjust == "hfq":
        res = requests.get(zh_sina_kcb_stock_hfq_url.format(symbol))
        hfq_factor_df = pd.DataFrame(
            eval(res.text.split("=")[1].split("\n")[0])["data"]
        )
        hfq_factor_df.columns = ["date", "hfq_factor"]
        hfq_factor_df.index = pd.to_datetime(hfq_factor_df.date)
        del hfq_factor_df["date"]

        temp_df = pd.merge(
            temp_df, hfq_factor_df, left_index=True, right_index=True, how="left"
        )
        try:
            # try for pandas >= 2.1.0
            temp_df.ffill(inplace=True)
        except Exception:
            try:
                # try for pandas < 2.1.0
                temp_df.fillna(method="ffill", inplace=True)
            except Exception as e:
                print("Error:", e)
        temp_df = temp_df.astype(float)
        temp_df["open"] = temp_df["open"] * temp_df["hfq_factor"]
        temp_df["high"] = temp_df["high"] * temp_df["hfq_factor"]
        temp_df["close"] = temp_df["close"] * temp_df["hfq_factor"]
        temp_df["low"] = temp_df["low"] * temp_df["hfq_factor"]
        temp_df = temp_df.iloc[:, :-1]
        temp_df.reset_index(inplace=True)
        temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
        return temp_df

    if adjust == "qfq":
        res = requests.get(zh_sina_kcb_stock_qfq_url.format(symbol))
        qfq_factor_df = pd.DataFrame(
            eval(res.text.split("=")[1].split("\n")[0])["data"]
        )
        qfq_factor_df.columns = ["date", "qfq_factor"]
        qfq_factor_df.index = pd.to_datetime(qfq_factor_df.date)
        del qfq_factor_df["date"]

        temp_df = pd.merge(
            temp_df, qfq_factor_df, left_index=True, right_index=True, how="left"
        )
        try:
            # try for pandas >= 2.1.0
            temp_df.ffill(inplace=True)
        except Exception:
            try:
                # try for pandas < 2.1.0
                temp_df.fillna(method="ffill", inplace=True)
            except Exception as e:
                print("Error:", e)
        temp_df = temp_df.astype(float)
        temp_df["open"] = temp_df["open"] / temp_df["qfq_factor"]
        temp_df["high"] = temp_df["high"] / temp_df["qfq_factor"]
        temp_df["close"] = temp_df["close"] / temp_df["qfq_factor"]
        temp_df["low"] = temp_df["low"] / temp_df["qfq_factor"]
        temp_df = temp_df.iloc[:, :-1]
        temp_df.reset_index(inplace=True)
        temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
        return temp_df

    if adjust == "hfq-factor":
        res = requests.get(zh_sina_kcb_stock_hfq_url.format(symbol))
        hfq_factor_df = pd.DataFrame(
            eval(res.text.split("=")[1].split("\n")[0])["data"]
        )
        hfq_factor_df.columns = ["date", "hfq_factor"]
        hfq_factor_df.index = pd.to_datetime(hfq_factor_df.date)
        del hfq_factor_df["date"]
        hfq_factor_df.reset_index(inplace=True)
        hfq_factor_df["date"] = pd.to_datetime(hfq_factor_df["date"]).dt.date
        return hfq_factor_df

    if adjust == "qfq-factor":
        res = requests.get(zh_sina_kcb_stock_qfq_url.format(symbol))
        qfq_factor_df = pd.DataFrame(
            eval(res.text.split("=")[1].split("\n")[0])["data"]
        )
        qfq_factor_df.columns = ["date", "qfq_factor"]
        qfq_factor_df.index = pd.to_datetime(qfq_factor_df.date)
        del qfq_factor_df["date"]
        qfq_factor_df.reset_index(inplace=True)
        qfq_factor_df["date"] = pd.to_datetime(qfq_factor_df["date"]).dt.date
        return qfq_factor_df


if __name__ == "__main__":
    stock_zh_kcb_daily_qfq_df = stock_zh_kcb_daily(symbol="sh688399", adjust="qfq")
    print(stock_zh_kcb_daily_qfq_df)

    stock_zh_kcb_daily_hfq_df = stock_zh_kcb_daily(symbol="sh688399", adjust="hfq")
    print(stock_zh_kcb_daily_hfq_df)

    stock_zh_kcb_daily_df = stock_zh_kcb_daily(symbol="sh688399", adjust="qfq-factor")
    print(stock_zh_kcb_daily_df)

    stock_zh_kcb_spot_df = stock_zh_kcb_spot()
    print(stock_zh_kcb_spot_df)
