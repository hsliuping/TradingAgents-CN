#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/7/22 18:30
Desc: 新浪财经-B股-实时行情数据和历史行情数据(包含前复权和后复权因子)
https://finance.sina.com.cn/realstock/company/sh689009/nc.shtml
"""

import json
import re
from functools import lru_cache

import pandas as pd
import requests
import py_mini_racer

from akshare.stock.cons import (
    zh_sina_a_stock_url,
    zh_sina_a_stock_hist_url,
    hk_js_decode,
    zh_sina_a_stock_hfq_url,
    zh_sina_a_stock_qfq_url,
    zh_sina_a_stock_amount_url,
)
from akshare.utils import demjson


@lru_cache()
def _get_zh_b_page_count() -> int:
    """
    所有股票的总页数
    https://vip.stock.finance.sina.com.cn/mkt/#hs_b
    :return: 需要采集的股票总页数
    :rtype: int
    """
    url = (
        "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        "Market_Center.getHQNodeStockCount?node=hs_b"
    )
    r = requests.get(url)
    page_count = int(re.findall(re.compile(r"\d+"), r.text)[0]) / 80
    if isinstance(page_count, int):
        return page_count
    else:
        return int(page_count) + 1


def stock_zh_b_spot() -> pd.DataFrame:
    """
    新浪财经-所有 B 股的实时行情数据; 重复运行本函数会被新浪暂时封 IP
    https://vip.stock.finance.sina.com.cn/mkt/#hs_b
    :return: 所有股票的实时行情数据
    :rtype: pandas.DataFrame
    """
    page_count = _get_zh_b_page_count()
    zh_sina_stock_payload_copy = {
        "page": "1",
        "num": "80",
        "sort": "symbol",
        "asc": "1",
        "node": "hs_b",
        "symbol": "",
        "_s_r_a": "page",
    }
    big_df = pd.DataFrame()
    for page in range(1, page_count + 1):
        zh_sina_stock_payload_copy.update({"page": page})
        r = requests.get(zh_sina_a_stock_url, params=zh_sina_stock_payload_copy)
        data_json = demjson.decode(r.text)
        big_df = pd.concat(objs=[big_df, pd.DataFrame(data_json)], ignore_index=True)
    big_df.columns = [
        "代码",
        "_",
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
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
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
        ]
    ]
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["涨跌额"] = pd.to_numeric(big_df["涨跌额"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["买入"] = pd.to_numeric(big_df["买入"], errors="coerce")
    big_df["卖出"] = pd.to_numeric(big_df["卖出"], errors="coerce")
    big_df["昨收"] = pd.to_numeric(big_df["昨收"], errors="coerce")
    big_df["今开"] = pd.to_numeric(big_df["今开"], errors="coerce")
    big_df["最高"] = pd.to_numeric(big_df["最高"], errors="coerce")
    big_df["最低"] = pd.to_numeric(big_df["最低"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["成交额"] = pd.to_numeric(big_df["成交额"], errors="coerce")
    return big_df


def stock_zh_b_daily(
    symbol: str = "sh900901",
    start_date: str = "19900101",
    end_date: str = "21000118",
    adjust: str = "",
) -> pd.DataFrame:
    """
    新浪财经-B 股-个股的历史行情数据, 大量抓取容易封 IP
    https://finance.sina.com.cn/realstock/company/sh900901/nc.shtml
    :param start_date: 20201103; 开始日期
    :type start_date: str
    :param end_date: 20201103; 结束日期
    :type end_date: str
    :param symbol: sh600000
    :type symbol: str
    :param adjust: 默认为空: 返回不复权的数据; qfq: 返回前复权后的数据; hfq: 返回后复权后的数据; hfq-factor: 返回后复权因子; qfq-factor: 返回前复权因子
    :type adjust: str
    :return: specific data
    :rtype: pandas.DataFrame
    """

    def _fq_factor(method: str) -> pd.DataFrame:
        if method == "hfq":
            r = requests.get(zh_sina_a_stock_hfq_url.format(symbol))
            hfq_factor_df = pd.DataFrame(
                eval(r.text.split("=")[1].split("\n")[0])["data"]
            )
            if hfq_factor_df.shape[0] == 0:
                raise ValueError("sina hfq factor not available")
            hfq_factor_df.columns = ["date", "hfq_factor"]
            hfq_factor_df.index = pd.to_datetime(hfq_factor_df.date)
            del hfq_factor_df["date"]
            hfq_factor_df.reset_index(inplace=True)
            return hfq_factor_df
        else:
            r = requests.get(zh_sina_a_stock_qfq_url.format(symbol))
            qfq_factor_df = pd.DataFrame(
                eval(r.text.split("=")[1].split("\n")[0])["data"]
            )
            if qfq_factor_df.shape[0] == 0:
                raise ValueError("sina hfq factor not available")
            qfq_factor_df.columns = ["date", "qfq_factor"]
            qfq_factor_df.index = pd.to_datetime(qfq_factor_df.date)
            del qfq_factor_df["date"]
            qfq_factor_df.reset_index(inplace=True)
            return qfq_factor_df

    if adjust in ("hfq-factor", "qfq-factor"):
        return _fq_factor(adjust.split("-")[0])

    r = requests.get(zh_sina_a_stock_hist_url.format(symbol))
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(hk_js_decode)
    dict_list = js_code.call(
        "d", r.text.split("=")[1].split(";")[0].replace('"', "")
    )  # 执行js解密代码
    data_df = pd.DataFrame(dict_list)
    data_df.index = pd.to_datetime(data_df["date"]).dt.date
    del data_df["date"]
    del data_df["amount"]
    del data_df["prevclose"]

    data_df = data_df.astype("float")
    r = requests.get(zh_sina_a_stock_amount_url.format(symbol, symbol))
    amount_data_json = demjson.decode(r.text[r.text.find("[") : r.text.rfind("]") + 1])
    amount_data_df = pd.DataFrame(amount_data_json)
    amount_data_df.index = pd.to_datetime(amount_data_df.date)
    del amount_data_df["date"]
    temp_df = pd.merge(
        data_df, amount_data_df, left_index=True, right_index=True, how="outer"
    )
    temp_df.ffill(inplace=True)
    temp_df = temp_df.astype(float)
    temp_df["amount"] = temp_df["amount"] * 10000
    temp_df["turnover"] = temp_df["volume"] / temp_df["amount"]
    temp_df.columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "outstanding_share",
        "turnover",
    ]
    if adjust == "":
        temp_df = temp_df[start_date:end_date]
        temp_df.drop_duplicates(
            subset=["open", "high", "low", "close", "volume"], inplace=True
        )
        temp_df["open"] = round(temp_df["open"], 2)
        temp_df["high"] = round(temp_df["high"], 2)
        temp_df["low"] = round(temp_df["low"], 2)
        temp_df["close"] = round(temp_df["close"], 2)
        temp_df.dropna(inplace=True)
        temp_df.drop_duplicates(inplace=True)
        temp_df.reset_index(inplace=True)
        return temp_df

    if adjust == "hfq":
        r = requests.get(zh_sina_a_stock_hfq_url.format(symbol))
        hfq_factor_df = pd.DataFrame(eval(r.text.split("=")[1].split("\n")[0])["data"])
        hfq_factor_df.columns = ["date", "hfq_factor"]
        hfq_factor_df.index = pd.to_datetime(hfq_factor_df.date)
        del hfq_factor_df["date"]
        temp_df = pd.merge(
            temp_df, hfq_factor_df, left_index=True, right_index=True, how="outer"
        )
        temp_df.ffill(inplace=True)
        temp_df = temp_df.astype(float)
        temp_df.dropna(inplace=True)
        temp_df.drop_duplicates(
            subset=["open", "high", "low", "close", "volume"], inplace=True
        )
        temp_df["open"] = temp_df["open"] * temp_df["hfq_factor"]
        temp_df["high"] = temp_df["high"] * temp_df["hfq_factor"]
        temp_df["close"] = temp_df["close"] * temp_df["hfq_factor"]
        temp_df["low"] = temp_df["low"] * temp_df["hfq_factor"]
        temp_df = temp_df.iloc[:, :-1]
        temp_df = temp_df[start_date:end_date]
        temp_df["open"] = round(temp_df["open"], 2)
        temp_df["high"] = round(temp_df["high"], 2)
        temp_df["low"] = round(temp_df["low"], 2)
        temp_df["close"] = round(temp_df["close"], 2)
        temp_df.dropna(inplace=True)
        temp_df.reset_index(inplace=True)
        return temp_df

    if adjust == "qfq":
        r = requests.get(zh_sina_a_stock_qfq_url.format(symbol))
        qfq_factor_df = pd.DataFrame(eval(r.text.split("=")[1].split("\n")[0])["data"])
        qfq_factor_df.columns = ["date", "qfq_factor"]
        qfq_factor_df.index = pd.to_datetime(qfq_factor_df.date)
        del qfq_factor_df["date"]
        temp_df = pd.merge(
            temp_df, qfq_factor_df, left_index=True, right_index=True, how="outer"
        )
        temp_df.ffill(inplace=True)
        temp_df = temp_df.astype(float)
        temp_df.dropna(inplace=True)
        temp_df.drop_duplicates(
            subset=["open", "high", "low", "close", "volume"], inplace=True
        )
        temp_df["open"] = temp_df["open"] / temp_df["qfq_factor"]
        temp_df["high"] = temp_df["high"] / temp_df["qfq_factor"]
        temp_df["close"] = temp_df["close"] / temp_df["qfq_factor"]
        temp_df["low"] = temp_df["low"] / temp_df["qfq_factor"]
        temp_df = temp_df.iloc[:, :-1]
        temp_df = temp_df[start_date:end_date]
        temp_df["open"] = round(temp_df["open"], 2)
        temp_df["high"] = round(temp_df["high"], 2)
        temp_df["low"] = round(temp_df["low"], 2)
        temp_df["close"] = round(temp_df["close"], 2)
        temp_df.dropna(inplace=True)
        temp_df.reset_index(inplace=True)
        return temp_df


def stock_zh_b_minute(
    symbol: str = "sh900901", period: str = "1", adjust: str = ""
) -> pd.DataFrame:
    """
    股票及股票指数历史行情数据-分钟数据
    https://finance.sina.com.cn/realstock/company/sh900901/nc.shtml
    :param symbol: sh900901
    :type symbol: str
    :param period: 1, 5, 15, 30, 60 分钟的数据
    :type period: str
    :param adjust: 默认为空: 返回不复权的数据; qfq: 返回前复权后的数据; hfq: 返回后复权后的数据;
    :type adjust: str
    :return: specific data
    :rtype: pandas.DataFrame
    """
    url = (
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData"
    )
    params = {
        "symbol": symbol,
        "scale": period,
        "datalen": "1970",
    }
    r = requests.get(url, params=params)
    temp_df = pd.DataFrame(json.loads(r.text.split("=(")[1].split(");")[0])).iloc[:, :6]
    if temp_df.empty:
        return pd.DataFrame()
    try:
        stock_zh_b_daily(symbol=symbol, adjust="qfq")
    except:  # noqa: E722
        return temp_df

    if adjust == "":
        return temp_df

    if adjust == "qfq":
        temp_df[["date", "time"]] = temp_df["day"].str.split(" ", expand=True)
        # 处理没有最后一分钟的情况
        need_df = temp_df[
            [
                True if "09:31:00" <= item <= "15:00:00" else False
                for item in temp_df["time"]
            ]
        ]
        need_df.drop_duplicates(subset=["date"], keep="last", inplace=True)
        need_df.index = pd.to_datetime(need_df["date"])
        stock_zh_b_daily_qfq_df = stock_zh_b_daily(symbol=symbol, adjust="qfq")
        stock_zh_b_daily_qfq_df.index = pd.to_datetime(stock_zh_b_daily_qfq_df["date"])
        result_df = stock_zh_b_daily_qfq_df.iloc[-len(need_df) :, :]["close"].astype(
            float
        ) / need_df["close"].astype(float)
        temp_df.index = pd.to_datetime(temp_df["date"])
        merged_df = pd.merge(temp_df, result_df, left_index=True, right_index=True)
        merged_df["open"] = merged_df["open"].astype(float) * merged_df["close_y"]
        merged_df["high"] = merged_df["high"].astype(float) * merged_df["close_y"]
        merged_df["low"] = merged_df["low"].astype(float) * merged_df["close_y"]
        merged_df["close"] = merged_df["close_x"].astype(float) * merged_df["close_y"]
        temp_df = merged_df[["day", "open", "high", "low", "close", "volume"]]
        temp_df.reset_index(drop=True, inplace=True)
        return temp_df
    if adjust == "hfq":
        temp_df[["date", "time"]] = temp_df["day"].str.split(" ", expand=True)
        # 处理没有最后一分钟的情况
        need_df = temp_df[
            [
                True if "09:31:00" <= item <= "15:00:00" else False
                for item in temp_df["time"]
            ]
        ]
        need_df.drop_duplicates(subset=["date"], keep="last", inplace=True)
        need_df.index = pd.to_datetime(need_df["date"])
        stock_zh_b_daily_hfq_df = stock_zh_b_daily(symbol=symbol, adjust="hfq")
        stock_zh_b_daily_hfq_df.index = pd.to_datetime(stock_zh_b_daily_hfq_df["date"])
        result_df = stock_zh_b_daily_hfq_df.iloc[-len(need_df) :, :]["close"].astype(
            float
        ) / need_df["close"].astype(float)
        temp_df.index = pd.to_datetime(temp_df["date"])
        merged_df = pd.merge(temp_df, result_df, left_index=True, right_index=True)
        merged_df["open"] = merged_df["open"].astype(float) * merged_df["close_y"]
        merged_df["high"] = merged_df["high"].astype(float) * merged_df["close_y"]
        merged_df["low"] = merged_df["low"].astype(float) * merged_df["close_y"]
        merged_df["close"] = merged_df["close_x"].astype(float) * merged_df["close_y"]
        temp_df = merged_df[["day", "open", "high", "low", "close", "volume"]]
        temp_df.reset_index(drop=True, inplace=True)
        return temp_df


if __name__ == "__main__":
    stock_zh_b_daily_hfq_df_one = stock_zh_b_daily(
        symbol="sh900901", start_date="20071103", end_date="20240916", adjust=""
    )
    print(stock_zh_b_daily_hfq_df_one)

    stock_zh_b_daily_hfq_df_three = stock_zh_b_daily(
        symbol="sh900901", start_date="19900103", end_date="20240722", adjust="hfq"
    )
    print(stock_zh_b_daily_hfq_df_three)

    stock_zh_b_daily_hfq_df_two = stock_zh_b_daily(
        symbol="sh900901", start_date="20101103", end_date="20210510"
    )
    print(stock_zh_b_daily_hfq_df_two)

    qfq_factor_df = stock_zh_b_daily(symbol="sh900901", adjust="qfq-factor")
    print(qfq_factor_df)

    hfq_factor_df = stock_zh_b_daily(symbol="sh900901", adjust="hfq-factor")
    print(hfq_factor_df)

    stock_zh_b_daily_hfq_factor_df = stock_zh_b_daily(
        symbol="sh900901", adjust="hfq-factor"
    )
    print(stock_zh_b_daily_hfq_factor_df)

    stock_zh_b_daily_df = stock_zh_b_daily(symbol="sh900901")
    print(stock_zh_b_daily_df)

    stock_zh_b_spot_df = stock_zh_b_spot()
    print(stock_zh_b_spot_df)

    stock_zh_b_minute_df = stock_zh_b_minute(symbol="sh900901", period="5", adjust="")
    print(stock_zh_b_minute_df)

    stock_zh_b_minute_df = stock_zh_b_minute(symbol="sh900901", period="1", adjust="")
    print(stock_zh_b_minute_df)

    stock_zh_b_daily_qfq_df = stock_zh_b_daily(
        symbol="sh900901", start_date="20101103", end_date="20201116", adjust="qfq"
    )
    print(stock_zh_b_daily_qfq_df)

    stock_zh_b_daily_hfq_df = stock_zh_b_daily(
        symbol="sh900901", start_date="20201103", end_date="20201116", adjust="hfq"
    )
    print(stock_zh_b_daily_hfq_df)

    qfq_factor_df = stock_zh_b_daily(symbol="sh900901", adjust="qfq-factor")
    print(qfq_factor_df)

    hfq_factor_df = stock_zh_b_daily(symbol="sh900901", adjust="hfq-factor")
    print(hfq_factor_df)

    stock_zh_b_minute_df = stock_zh_b_minute(
        symbol="sh900901", period="1", adjust="qfq"
    )
    print(stock_zh_b_minute_df)
