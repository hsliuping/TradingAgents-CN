#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/10 18:30
Desc: 股票指数数据-新浪-东财-腾讯
所有指数-实时行情数据和历史行情数据
https://finance.sina.com.cn/realstock/company/sz399552/nc.shtml
"""

import datetime
import re

import pandas as pd
import py_mini_racer
import requests

from akshare.index.cons import (
    zh_sina_index_stock_payload,
    zh_sina_index_stock_url,
    zh_sina_index_stock_count_url,
    zh_sina_index_stock_hist_url,
)
from akshare.stock.cons import hk_js_decode
from akshare.utils import demjson
from akshare.utils.func import fetch_paginated_data
from akshare.utils.tqdm import get_tqdm


def _replace_comma(x):
    """
    去除单元格中的 ","
    :param x: 单元格元素
    :type x: str
    :return: 处理后的值或原值
    :rtype: str
    """
    if "," in str(x):
        return str(x).replace(",", "")
    else:
        return x


def get_zh_index_page_count() -> int:
    """
    指数的总页数
    https://vip.stock.finance.sina.com.cn/mkt/#hs_s
    :return: 需要抓取的指数的总页数
    :rtype: int
    """
    res = requests.get(zh_sina_index_stock_count_url)
    page_count = int(re.findall(re.compile(r"\d+"), res.text)[0]) / 80
    if isinstance(page_count, int):
        return page_count
    else:
        return int(page_count) + 1


def stock_zh_index_spot_sina() -> pd.DataFrame:
    """
    新浪财经-行情中心首页-A股-分类-所有指数
    大量采集会被目标网站服务器封禁 IP, 如果被封禁 IP, 请 10 分钟后再试
    https://vip.stock.finance.sina.com.cn/mkt/#hs_s
    :return: 所有指数的实时行情数据
    :rtype: pandas.DataFrame
    """
    big_df = pd.DataFrame()
    page_count = get_zh_index_page_count()
    zh_sina_stock_payload_copy = zh_sina_index_stock_payload.copy()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_count + 1), leave=False):
        zh_sina_stock_payload_copy.update({"page": page})
        res = requests.get(zh_sina_index_stock_url, params=zh_sina_stock_payload_copy)
        data_json = demjson.decode(res.text)
        big_df = pd.concat(objs=[big_df, pd.DataFrame(data_json)], ignore_index=True)
    big_df = big_df.map(_replace_comma)
    big_df["trade"] = pd.to_numeric(big_df["trade"], errors="coerce")
    big_df["pricechange"] = pd.to_numeric(big_df["pricechange"], errors="coerce")
    big_df["changepercent"] = pd.to_numeric(big_df["changepercent"], errors="coerce")
    big_df["buy"] = pd.to_numeric(big_df["buy"], errors="coerce")
    big_df["sell"] = pd.to_numeric(big_df["sell"], errors="coerce")
    big_df["settlement"] = pd.to_numeric(big_df["settlement"], errors="coerce")
    big_df["open"] = pd.to_numeric(big_df["open"], errors="coerce")
    big_df["high"] = pd.to_numeric(big_df["high"], errors="coerce")
    big_df["low"] = pd.to_numeric(big_df["low"], errors="coerce")
    big_df.columns = [
        "代码",
        "名称",
        "最新价",
        "涨跌额",
        "涨跌幅",
        "_",
        "_",
        "昨收",
        "今开",
        "最高",
        "最低",
        "成交量",
        "成交额",
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
    big_df["昨收"] = pd.to_numeric(big_df["昨收"], errors="coerce")
    big_df["今开"] = pd.to_numeric(big_df["今开"], errors="coerce")
    big_df["最高"] = pd.to_numeric(big_df["最高"], errors="coerce")
    big_df["最低"] = pd.to_numeric(big_df["最低"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["成交额"] = pd.to_numeric(big_df["成交额"], errors="coerce")
    return big_df


def __stock_zh_main_spot_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-沪深重要指数
    https://quote.eastmoney.com/center/hszs.html
    :return: 指数的实时行情数据
    :rtype: pandas.DataFrame
    """
    url = "https://33.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "dect": "1",
        "wbp2u": "|0|0|0|web",
        "fid": "",
        "fs": "b:MK0010",
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,"
        "f23,f24,f25,f26,f22,f11,f62,f128,f136,f115,f152",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["diff"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"].astype(int) + 1
    temp_df.rename(
        columns={
            "index": "序号",
            "f2": "最新价",
            "f3": "涨跌幅",
            "f4": "涨跌额",
            "f5": "成交量",
            "f6": "成交额",
            "f7": "振幅",
            "f10": "量比",
            "f12": "代码",
            "f14": "名称",
            "f15": "最高",
            "f16": "最低",
            "f17": "今开",
            "f18": "昨收",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "代码",
            "名称",
            "最新价",
            "涨跌幅",
            "涨跌额",
            "成交量",
            "成交额",
            "振幅",
            "最高",
            "最低",
            "今开",
            "昨收",
            "量比",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce")
    temp_df["量比"] = pd.to_numeric(temp_df["量比"], errors="coerce")
    return temp_df


def stock_zh_index_spot_em(symbol: str = "上证系列指数") -> pd.DataFrame:
    """
    东方财富网-行情中心-沪深京指数
    https://quote.eastmoney.com/center/gridlist.html#index_sz
    :param symbol: "上证系列指数"; choice of {"沪深重要指数", "上证系列指数", "深证系列指数", "指数成份", "中证系列指数"}
    :type symbol: str
    :return: 指数的实时行情数据
    :rtype: pandas.DataFrame
    """
    if symbol == "沪深重要指数":
        return __stock_zh_main_spot_em()

    url = "https://48.push2.eastmoney.com/api/qt/clist/get"
    symbol_map = {
        "上证系列指数": "m:1+t:1",
        "深证系列指数": "m:0 t:5",
        "指数成份": "m:1+s:3,m:0+t:5",
        "中证系列指数": "m:2",
    }
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "wbp2u": "|0|0|0|web",
        "fid": "f12",
        "fs": symbol_map[symbol],
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,"
        "f26,f22,f33,f11,f62,f128,f136,f115,f152",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.rename(
        columns={
            "index": "序号",
            "f2": "最新价",
            "f3": "涨跌幅",
            "f4": "涨跌额",
            "f5": "成交量",
            "f6": "成交额",
            "f7": "振幅",
            "f10": "量比",
            "f12": "代码",
            "f14": "名称",
            "f15": "最高",
            "f16": "最低",
            "f17": "今开",
            "f18": "昨收",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "代码",
            "名称",
            "最新价",
            "涨跌幅",
            "涨跌额",
            "成交量",
            "成交额",
            "振幅",
            "最高",
            "最低",
            "今开",
            "昨收",
            "量比",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce")
    temp_df["量比"] = pd.to_numeric(temp_df["量比"], errors="coerce")
    return temp_df


def stock_zh_index_daily(symbol: str = "sh000922") -> pd.DataFrame:
    """
    新浪财经-指数-历史行情数据, 大量抓取容易封 IP
    https://finance.sina.com.cn/realstock/company/sh000909/nc.shtml
    :param symbol: sz399998, 指定指数代码
    :type symbol: str
    :return: 历史行情数据
    :rtype: pandas.DataFrame
    """
    params = {"d": "2020_2_4"}
    res = requests.get(zh_sina_index_stock_hist_url.format(symbol), params=params)
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(hk_js_decode)
    dict_list = js_code.call(
        "d", res.text.split("=")[1].split(";")[0].replace('"', "")
    )  # 执行js解密代码
    temp_df = pd.DataFrame(dict_list)
    temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df["open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    temp_df["high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df["low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df["volume"] = pd.to_numeric(temp_df["volume"], errors="coerce")
    return temp_df


def get_tx_start_year(symbol: str = "sh000919") -> str:
    """
    腾讯证券-获取所有股票数据的第一天, 注意这个数据是腾讯证券的历史数据第一天
    https://gu.qq.com/sh000919/zs
    :param symbol: 带市场标识的股票代码
    :type symbol: str
    :return: 开始日期
    :rtype: str
    """
    url = "https://web.ifzq.gtimg.cn/other/klineweb/klineWeb/weekTrends"
    params = {
        "code": symbol,
        "type": "qfq",
        "_var": "trend_qfq",
        "r": "0.3506048543943414",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    if not demjson.decode(data_text[data_text.find("={") + 1 :])["data"]:
        url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
        params = {
            "_var": "kline_dayqfq",
            "param": f"{symbol},day,,,320,qfq",
            "r": "0.751892490072597",
        }
        r = requests.get(url, params=params)
        data_text = r.text
        start_date = demjson.decode(data_text[data_text.find("={") + 1 :])["data"][
            symbol
        ]["day"][0][0]
        return start_date
    start_date = demjson.decode(data_text[data_text.find("={") + 1 :])["data"][0][0]
    return start_date


def stock_zh_index_daily_tx(symbol: str = "sz980017") -> pd.DataFrame:
    """
    腾讯证券-日频-股票或者指数历史数据
    作为 ak.stock_zh_index_daily() 的补充, 因为在新浪中有部分指数数据缺失
    注意都是: 前复权, 不同网站复权方式不同, 不可混用数据
    https://gu.qq.com/sh000919/zs
    :param symbol: 带市场标识的股票或者指数代码
    :type symbol: str
    :return: 前复权的股票和指数数据
    :rtype: pandas.DataFrame
    """
    start_date = get_tx_start_year(symbol=symbol)
    url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
    range_start = int(start_date.split("-")[0])
    range_end = datetime.date.today().year + 1
    temp_df = pd.DataFrame()
    tqdm = get_tqdm()
    for year in tqdm(range(range_start, range_end), leave=False):
        params = {
            "_var": "kline_dayqfq",
            "param": f"{symbol},day,{year}-01-01,{year + 1}-12-31,640,qfq",
            "r": "0.8205512681390605",
        }
        res = requests.get(url, params=params)
        text = res.text
        try:
            inner_temp_df = pd.DataFrame(
                demjson.decode(text[text.find("={") + 1 :])["data"][symbol]["day"]
            )
        except:  # noqa: E722
            inner_temp_df = pd.DataFrame(
                demjson.decode(text[text.find("={") + 1 :])["data"][symbol]["qfqday"]
            )
        temp_df = pd.concat(objs=[temp_df, inner_temp_df], ignore_index=True)
    if temp_df.shape[1] == 6:
        temp_df.columns = ["date", "open", "close", "high", "low", "amount"]
    else:
        temp_df = temp_df.iloc[:, :6]
        temp_df.columns = ["date", "open", "close", "high", "low", "amount"]
    temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df["open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    temp_df["high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df["low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df["amount"] = pd.to_numeric(temp_df["amount"], errors="coerce")
    temp_df.drop_duplicates(inplace=True, ignore_index=True)
    return temp_df


def stock_zh_index_daily_em(
    symbol: str = "csi931151",
    start_date: str = "19900101",
    end_date: str = "20500101",
) -> pd.DataFrame:
    """
    东方财富网-股票指数数据
    https://quote.eastmoney.com/center/hszs.html
    :param symbol: 带市场标识的指数代码; sz: 深交所, sh: 上交所, csi: 中信指数 + id(000905)
    :type symbol: str
    :param start_date: 开始时间
    :type start_date: str
    :param end_date: 结束时间
    :type end_date: str
    :return: 指数数据
    :rtype: pandas.DataFrame
    """
    market_map = {"sz": "0", "sh": "1", "csi": "2"}
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    if symbol.find("sz") != -1:
        secid = "{}.{}".format(market_map["sz"], symbol.replace("sz", ""))
    elif symbol.find("sh") != -1:
        secid = "{}.{}".format(market_map["sh"], symbol.replace("sh", ""))
    elif symbol.find("csi") != -1:
        secid = "{}.{}".format(market_map["csi"], symbol.replace("csi", ""))
    else:
        return pd.DataFrame()
    params = {
        "cb": "jQuery1124033485574041163946_1596700547000",
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "klt": "101",  # 日频率
        "fqt": "0",
        "beg": start_date,
        "end": end_date,
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -2])
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    # check temp_df data availability before further transformations which may raise errors
    if temp_df.empty:
        return pd.DataFrame()
    temp_df.columns = ["date", "open", "close", "high", "low", "volume", "amount", "_"]
    temp_df = temp_df[["date", "open", "close", "high", "low", "volume", "amount"]]
    temp_df["open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    temp_df["high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df["low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df["volume"] = pd.to_numeric(temp_df["volume"], errors="coerce")
    temp_df["amount"] = pd.to_numeric(temp_df["amount"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_zh_index_daily_df = stock_zh_index_daily(symbol="sh000510")
    print(stock_zh_index_daily_df)

    stock_zh_index_spot_sina_df = stock_zh_index_spot_sina()
    print(stock_zh_index_spot_sina_df)

    stock_zh_index_spot_em_df = stock_zh_index_spot_em(symbol="沪深重要指数")
    print(stock_zh_index_spot_em_df)

    stock_zh_index_spot_em_df = stock_zh_index_spot_em(symbol="上证系列指数")
    print(stock_zh_index_spot_em_df)

    stock_zh_index_spot_em_df = stock_zh_index_spot_em(symbol="深证系列指数")
    print(stock_zh_index_spot_em_df)

    stock_zh_index_spot_em_df = stock_zh_index_spot_em(symbol="指数成份")
    print(stock_zh_index_spot_em_df)

    stock_zh_index_spot_em_df = stock_zh_index_spot_em(symbol="中证系列指数")
    print(stock_zh_index_spot_em_df)

    stock_zh_index_daily_tx_df = stock_zh_index_daily_tx(symbol="sh000919")
    print(stock_zh_index_daily_tx_df)

    stock_zh_index_daily_em_df = stock_zh_index_daily_em(symbol="sz399812")
    print(stock_zh_index_daily_em_df)
