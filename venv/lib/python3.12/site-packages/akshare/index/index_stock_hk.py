#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/15 22:30
Desc: 港股股票指数数据-新浪-东财
所有指数-实时行情数据和历史行情数据
https://finance.sina.com.cn/realstock/company/sz399552/nc.shtml
https://quote.eastmoney.com/gb/zsHSTECF2L.html
"""

import re

import pandas as pd
import requests
import py_mini_racer

from functools import lru_cache

from akshare.stock.cons import hk_js_decode
from akshare.utils.func import fetch_paginated_data


def _replace_comma(x) -> str:
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


def get_hk_index_page_count() -> int:
    """
    指数的总页数
    https://vip.stock.finance.sina.com.cn/mkt/#zs_hk
    :return: 需要抓取的指数的总页数
    :rtype: int
    """
    res = requests.get(
        "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getNameCount?node=zs_hk"
    )
    page_count = int(re.findall(re.compile(r"\d+"), res.text)[0]) / 80
    if isinstance(page_count, int):
        return page_count
    else:
        return int(page_count) + 1


def stock_hk_index_spot_sina() -> pd.DataFrame:
    """
    新浪财经-行情中心-港股指数
    大量采集会被目标网站服务器封禁 IP, 如果被封禁 IP, 请 10 分钟后再试
    https://vip.stock.finance.sina.com.cn/mkt/#zs_hk
    :return: 所有指数的实时行情数据
    :rtype: pandas.DataFrame
    """
    url = (
        "https://hq.sinajs.cn/rn=mtf2t&list=hkCES100,hkCES120,hkCES280,hkCES300,hkCESA80,hkCESG10,"
        "hkCESHKM,hkCSCMC,hkCSHK100,hkCSHKDIV,hkCSHKLC,hkCSHKLRE,hkCSHKMCS,hkCSHKME,hkCSHKPE,hkCSHKSE,"
        "hkCSI300,hkCSRHK50,hkGEM,hkHKL,hkHSCCI,hkHSCEI,hkHSI,hkHSMBI,hkHSMOGI,hkHSMPI,hkHSTECH,hkSSE180,"
        "hkSSE180GV,hkSSE380,hkSSE50,hkSSECEQT,hkSSECOMP,hkSSEDIV,hkSSEITOP,hkSSEMCAP,hkSSEMEGA,hkVHSI"
    )
    headers = {"Referer": "https://vip.stock.finance.sina.com.cn/"}
    r = requests.get(url, headers=headers)
    data_text = r.text
    data_list = [
        item.split('"')[1].split(",")
        for item in data_text.split("\n")
        if len(item.split('"')) > 1
    ]
    temp_df = pd.DataFrame(data_list)
    temp_df.columns = [
        "代码",
        "名称",
        "今开",
        "昨收",
        "最高",
        "最低",
        "最新价",
        "涨跌额",
        "涨跌幅",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df = temp_df[
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
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce")
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    return temp_df


def stock_hk_index_daily_sina(symbol: str = "CES100") -> pd.DataFrame:
    """
    新浪财经-港股指数-历史行情数据
    https://stock.finance.sina.com.cn/hkstock/quotes/CES100.html
    :param symbol: CES100, 港股指数代码
    :type symbol: str
    :return: 历史行情数据
    :rtype: pandas.DataFrame
    """
    url = f"https://finance.sina.com.cn/stock/hkstock/{symbol}/klc_kl.js"
    params = {"d": "2023_5_01"}
    res = requests.get(url, params=params)
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


def stock_hk_index_spot_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-港股-指数实时行情
    https://quote.eastmoney.com/center/gridlist.html#hk_index
    :return: 指数行情
    :rtype: pandas.DataFrame
    """
    url = "https://15.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "wbp2u": "|0|0|0|web",
        "fid": "f3",
        "fs": "m:124,m:125,m:305",
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
            "f12": "代码",
            "f13": "内部编号",
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
            "内部编号",
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "今开",
            "最高",
            "最低",
            "昨收",
            "成交量",
            "成交额",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    return temp_df


@lru_cache()
def _symbol_code_dict() -> dict:
    """
    缓存 ak.stock_hk_index_spot_em() 接口中的代码与内部编号
    https://quote.eastmoney.com/center/gridlist.html#hk_index
    :return: 代码与内部编号
    :rtype: dict
    """
    __stock_hk_index_spot_em_df = stock_hk_index_spot_em()
    symbol_code_dict = dict(
        zip(
            __stock_hk_index_spot_em_df["代码"], __stock_hk_index_spot_em_df["内部编号"]
        )
    )
    return symbol_code_dict


def stock_hk_index_daily_em(symbol: str = "HSTECF2L") -> pd.DataFrame:
    """
    东方财富网-港股-股票指数数据
    https://quote.eastmoney.com/gb/zsHSTECF2L.html
    :param symbol: 港股指数代码; 可以通过 ak.stock_hk_index_spot_em() 获取
    :type symbol: str
    :return: 指数数据
    :rtype: pandas.DataFrame
    """
    symbol_code_dict = _symbol_code_dict()
    symbol_code_dict.update(
        {
            "HSAHP": "100",
        }
    )
    symbol_str = f"{symbol_code_dict[symbol]}.{symbol}"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": symbol_str,
        "klt": "101",  # 日频率
        "fqt": "1",
        "lmt": "10000",
        "end": "20500000",
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "forcect": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    temp_df.columns = [
        "date",
        "open",
        "latest",
        "high",
        "low",
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
    temp_df = temp_df[["date", "open", "high", "low", "latest"]]
    temp_df["open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df["latest"] = pd.to_numeric(temp_df["latest"], errors="coerce")
    temp_df["high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df["low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_hk_index_spot_sina_df = stock_hk_index_spot_sina()
    print(stock_hk_index_spot_sina_df)

    stock_hk_index_daily_sina_df = stock_hk_index_daily_sina(symbol="CES100")
    print(stock_hk_index_daily_sina_df)

    stock_hk_index_spot_em_df = stock_hk_index_spot_em()
    print(stock_hk_index_spot_em_df)

    stock_hk_index_daily_em_df = stock_hk_index_daily_em(symbol="HSTECH")
    print(stock_hk_index_daily_em_df)
