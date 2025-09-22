#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/5 18:00
Desc: 新浪财经-外盘期货
https://finance.sina.com.cn/money/future/hf.html
"""

import time
from typing import Union, List

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.utils import demjson


def _get_real_name_list() -> list:
    """
    新浪-外盘期货所有品种的中文名称
    https://finance.sina.com.cn/money/future/hf.html
    :return: 外盘期货所有品种的中文名称
    :rtype: list
    """
    url = "https://finance.sina.com.cn/money/future/hf.html"
    r = requests.get(url)
    r.encoding = "gb2312"
    data_text = r.text
    need_text = data_text[
        data_text.find("var oHF_1 = ") + 12 : data_text.find("var oHF_2") - 2
    ].replace("\n\t", "")
    data_json = demjson.decode(need_text)
    name_list = [item[0].strip() for item in data_json.values()]
    return name_list


def futures_foreign_commodity_subscribe_exchange_symbol() -> list:
    """
    需要订阅的行情的代码
    https://finance.sina.com.cn/money/future/hf.html
    :return: 需要订阅的行情的代码
    :rtype: list
    """
    url = "https://finance.sina.com.cn/money/future/hf.html"
    r = requests.get(url)
    r.encoding = "gb2312"
    data_text = r.text
    data_json = demjson.decode(
        data_text[
            data_text.find("var oHF_1 = ") + 12 : data_text.find("var oHF_2 = ") - 2
        ]
    )
    code_list = list(data_json.keys())
    return code_list


def futures_hq_subscribe_exchange_symbol() -> pd.DataFrame:
    """
    将品种字典转化为 pandas.DataFrame
    https://finance.sina.com.cn/money/future/hf.html
    :return: 品种对应表
    :rtype: pandas.DataFrame
    """
    inner_dict = {
        "新加坡铁矿石": "FEF",
        "马棕油": "FCPO",
        "日橡胶": "RSS3",
        "美国原糖": "RS",
        "CME比特币期货": "BTC",
        "NYBOT-棉花": "CT",
        "LME镍3个月": "NID",
        "LME铅3个月": "PBD",
        "LME锡3个月": "SND",
        "LME锌3个月": "ZSD",
        "LME铝3个月": "AHD",
        "LME铜3个月": "CAD",
        "CBOT-黄豆": "S",
        "CBOT-小麦": "W",
        "CBOT-玉米": "C",
        "CBOT-黄豆油": "BO",
        "CBOT-黄豆粉": "SM",
        "日本橡胶": "TRB",
        "COMEX铜": "HG",
        "NYMEX天然气": "NG",
        "NYMEX原油": "CL",
        "COMEX白银": "SI",
        "COMEX黄金": "GC",
        "CME-瘦肉猪": "LHC",
        "布伦特原油": "OIL",
        "伦敦金": "XAU",
        "伦敦银": "XAG",
        "伦敦铂金": "XPT",
        "伦敦钯金": "XPD",
        "欧洲碳排放": "EUA",
    }
    temp_df = pd.DataFrame.from_dict(inner_dict, orient="index")
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["symbol", "code"]
    return temp_df


def futures_foreign_commodity_realtime(symbol: Union[str, List[str]]) -> pd.DataFrame:
    """
    新浪-外盘期货-行情数据
    https://finance.sina.com.cn/money/future/hf.html
    :param symbol: 通过调用 ak.futures_hq_subscribe_exchange_symbol() 函数来获取
    :type symbol: list or str
    :return: 行情数据
    :rtype: pandas.DataFrame
    """
    if isinstance(symbol, list):
        payload = "?list=" + ",".join(["hf_" + item for item in symbol])
    else:
        symbol = symbol.split(",")
        payload = "?list=" + ",".join(["hf_" + item for item in symbol])
    url = "https://hq.sinajs.cn/" + payload
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "hq.sinajs.cn",
        "Pragma": "no-cache",
        "Referer": "https://finance.sina.com.cn/",
        "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="97", "Chromium";v="97"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/97.0.4692.71 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    data_text = r.text
    data_df = pd.DataFrame(
        [
            item.strip().split("=")[1].split(",")
            for item in data_text.split(";")
            if item.strip() != ""
        ]
    )
    data_df.iloc[:, 0] = data_df.iloc[:, 0].str.replace('"', "")
    data_df.iloc[:, -1] = data_df.iloc[:, -1].str.replace('"', "")

    # 处理伦敦金 XAU 的情况
    if len(data_df.columns) == 14:
        data_df["temp"] = None

    data_df.columns = [
        "current_price",
        "-",
        "bid",
        "ask",
        "high",
        "low",
        "time",
        "last_settle_price",
        "open",
        "hold",
        "-",
        "-",
        "date",
        "symbol",
        "current_price_rmb",
    ]
    temp_symbol_code_df = futures_hq_subscribe_exchange_symbol()
    temp_symbol_code_dict = dict(
        zip(temp_symbol_code_df["code"], temp_symbol_code_df["symbol"])
    )
    data_df["symbol"] = [temp_symbol_code_dict[subscribe] for subscribe in symbol]
    data_df = data_df[
        [
            "symbol",
            "current_price",
            "current_price_rmb",
            "bid",
            "ask",
            "high",
            "low",
            "time",
            "last_settle_price",
            "open",
            "hold",
            "date",
        ]
    ]
    data_df.columns = [
        "名称",
        "最新价",
        "人民币报价",
        "买价",
        "卖价",
        "最高价",
        "最低价",
        "行情时间",
        "昨日结算价",
        "开盘价",
        "持仓量",
        "日期",
    ]
    data_df.dropna(how="all", inplace=True)
    data_df["最新价"] = pd.to_numeric(data_df["最新价"], errors="coerce")
    data_df["人民币报价"] = pd.to_numeric(data_df["人民币报价"], errors="coerce")
    data_df["买价"] = pd.to_numeric(data_df["买价"], errors="coerce")
    data_df["卖价"] = pd.to_numeric(data_df["卖价"], errors="coerce")
    data_df["最高价"] = pd.to_numeric(data_df["最高价"], errors="coerce")
    data_df["最低价"] = pd.to_numeric(data_df["最低价"], errors="coerce")
    data_df["昨日结算价"] = pd.to_numeric(data_df["昨日结算价"], errors="coerce")
    data_df["开盘价"] = pd.to_numeric(data_df["开盘价"], errors="coerce")
    data_df["持仓量"] = pd.to_numeric(data_df["持仓量"], errors="coerce")
    data_df["涨跌额"] = data_df["最新价"] - data_df["昨日结算价"]
    data_df["涨跌幅"] = (
        (data_df["最新价"] - data_df["昨日结算价"]) / data_df["昨日结算价"] * 100
    )
    data_df = data_df[
        [
            "名称",
            "最新价",
            "人民币报价",
            "涨跌额",
            "涨跌幅",
            "开盘价",
            "最高价",
            "最低价",
            "昨日结算价",
            "持仓量",
            "买价",
            "卖价",
            "行情时间",
            "日期",
        ]
    ]

    # 获取转换比例数据
    url = "https://finance.sina.com.cn/money/future/hf.html"
    r = requests.get(url)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, features="lxml")
    data_text = soup.find_all(name="script", attrs={"type": "text/javascript"})[
        -2
    ].string.strip()
    raw_text = data_text[data_text.find("oHF_1 = ") : data_text.find("oHF_2")]
    need_text = raw_text[raw_text.find("{") : raw_text.rfind("}") + 1]
    data_json = demjson.decode(need_text)
    price_mul = pd.DataFrame(
        [
            [item[0] for item in data_json.values()],
            [item[1][0] for item in data_json.values()],
        ]
    ).T
    price_mul.columns = ["symbol", "price"]
    price_mul = price_mul[price_mul["symbol"].isin(data_df["名称"])]
    price_mul.reset_index(inplace=True, drop=True)
    price_mul["price"] = pd.to_numeric(price_mul["price"], errors="coerce")

    # 获取汇率数据
    url = "https://hq.sinajs.cn/?list=USDCNY"
    r = requests.get(url, headers=headers)
    data_text = r.text
    usd_rmb = float(
        data_text[data_text.find('"') + 1 : data_text.find(",美元人民币")].split(",")[
            -1
        ]
    )

    # 计算人民币报价
    data_df["最新价"] = pd.to_numeric(data_df["最新价"], errors="coerce")
    data_df["人民币报价"] = data_df["最新价"] * price_mul["price"] * float(usd_rmb)
    data_df.dropna(thresh=4, inplace=True)
    return data_df


if __name__ == "__main__":
    futures_hq_subscribe_exchange_symbol_df = futures_hq_subscribe_exchange_symbol()
    print(futures_hq_subscribe_exchange_symbol_df)

    print("开始接收实时行情, 每秒刷新一次")
    subscribes = futures_foreign_commodity_subscribe_exchange_symbol()

    futures_foreign_commodity_realtime_df = futures_foreign_commodity_realtime(
        symbol="CT,NID"
    )
    print(futures_foreign_commodity_realtime_df)

    futures_foreign_commodity_realtime_df = futures_foreign_commodity_realtime(
        symbol=["XAU"]
    )
    print(futures_foreign_commodity_realtime_df)

    while True:
        futures_foreign_commodity_realtime_df = futures_foreign_commodity_realtime(
            symbol=subscribes
        )
        print(futures_foreign_commodity_realtime_df)
        time.sleep(3)
