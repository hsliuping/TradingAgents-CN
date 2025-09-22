#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/3/1 23:00
Desc: 新浪财经-期货的主力合约数据
https://finance.sina.com.cn/futuremarket/index.shtml
"""

from io import StringIO

import pandas as pd
import requests

from akshare.futures.cons import (
    zh_subscribe_exchange_symbol_url,
    zh_match_main_contract_url,
    zh_match_main_contract_payload,
)
from akshare.utils import demjson


def zh_subscribe_exchange_symbol(symbol: str = "dce") -> pd.DataFrame:
    """
    订阅指定交易所品种的代码
    https://finance.sina.com.cn/futuremarket/index.shtml
    :param symbol: choice of {"dce", "czce", "shfe", "cffex", "gfex"}
    :type symbol: str
    :return: 订阅指定交易所品种的代码
    :rtype: pandas.DataFrame
    """
    r = requests.get(zh_subscribe_exchange_symbol_url)
    r.encoding = "gb2312"
    data_text = r.text
    data_json = demjson.decode(
        data_text[data_text.find("{") : data_text.find("};") + 1]
    )
    if symbol == "czce":
        data_json["czce"].remove("郑州商品交易所")
        return pd.DataFrame(data_json["czce"])
    if symbol == "dce":
        data_json["dce"].remove("大连商品交易所")
        return pd.DataFrame(data_json["dce"])
    if symbol == "shfe":
        data_json["shfe"].remove("上海期货交易所")
        return pd.DataFrame(data_json["shfe"])
    if symbol == "cffex":
        data_json["cffex"].remove("中国金融期货交易所")
        return pd.DataFrame(data_json["cffex"])
    if symbol == "gfex":
        data_json["gfex"].remove("广州期货交易所")
        return pd.DataFrame(data_json["gfex"])


def match_main_contract(symbol: str = "shfe") -> pd.DataFrame:
    """
    指定交易所的所有可以提供数据的合约
    https://finance.sina.com.cn/futuremarket/index.shtml
    :param symbol: choice of {"dce", "czce", "shfe", "cffex", "gfex"}
    :type symbol: str
    :return: 指定交易所的所有可以提供数据的合约
    :rtype: pandas.DataFrame
    """
    subscribe_list = []
    exchange_symbol_list = zh_subscribe_exchange_symbol(symbol).iloc[:, 1].tolist()
    for item in exchange_symbol_list:
        zh_match_main_contract_payload.update({"node": item})
        res = requests.get(
            zh_match_main_contract_url, params=zh_match_main_contract_payload
        )
        data_json = demjson.decode(res.text)
        data_df = pd.DataFrame(data_json)
        try:
            main_contract = data_df[
                data_df["name"].str.contains("连续")
                & data_df["symbol"]
                .str.extract(r"([\w])(\d)")
                .iloc[:, 1]
                .str.contains("0")
            ].iloc[0, :3]
            subscribe_list.append(main_contract)
        except:  # noqa: E722
            # print(item, "无主力连续合约")
            continue
    # print("主力连续合约获取成功")
    temp_df = pd.DataFrame(subscribe_list)
    return temp_df


def futures_display_main_sina() -> pd.DataFrame:
    """
    新浪主力连续合约品种一览表
    https://finance.sina.com.cn/futuremarket/index.shtml
    :return: 新浪主力连续合约品种一览表
    :rtype: pandas.DataFrame
    """
    temp_df = pd.DataFrame()
    for item in ["dce", "czce", "shfe", "cffex", "gfex"]:
        temp_df = pd.concat([temp_df, match_main_contract(symbol=item)])
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


def futures_main_sina(
    symbol: str = "V0",
    start_date: str = "19900101",
    end_date: str = "22220101",
) -> pd.DataFrame:
    """
    新浪财经-期货-主力连续日数据
    https://vip.stock.finance.sina.com.cn/quotes_service/view/qihuohangqing.html#titlePos_1
    :param symbol: 通过 ak.futures_display_main_sina() 函数获取 symbol
    :type symbol: str
    :param start_date: 开始时间
    :type start_date: str
    :param end_date: 结束时间
    :type end_date: str
    :return: 主力连续日数据
    :rtype: pandas.DataFrame
    """
    trade_date = "20210817"
    trade_date = trade_date[:4] + "_" + trade_date[4:6] + "_" + trade_date[6:]
    url = f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{symbol}{trade_date}=/InnerFuturesNewService.getDailyKLine?symbol={symbol}&_={trade_date}"
    r = requests.get(url)
    data_text = r.text
    data_json = data_text[data_text.find("([") + 1 : data_text.rfind("])") + 1]
    temp_df = pd.read_json(StringIO(data_json))
    temp_df.columns = [
        "日期",
        "开盘价",
        "最高价",
        "最低价",
        "收盘价",
        "成交量",
        "持仓量",
        "动态结算价",
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df.set_index(keys=["日期"], inplace=True)
    temp_df.index = pd.to_datetime(temp_df.index)
    temp_df = temp_df[start_date:end_date]
    temp_df.reset_index(inplace=True)
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["开盘价"] = pd.to_numeric(temp_df["开盘价"], errors="coerce")
    temp_df["最高价"] = pd.to_numeric(temp_df["最高价"], errors="coerce")
    temp_df["最低价"] = pd.to_numeric(temp_df["最低价"], errors="coerce")
    temp_df["收盘价"] = pd.to_numeric(temp_df["收盘价"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["持仓量"] = pd.to_numeric(temp_df["持仓量"], errors="coerce")
    temp_df["动态结算价"] = pd.to_numeric(temp_df["动态结算价"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    futures_display_main_sina_df = futures_display_main_sina()
    print(futures_display_main_sina_df)

    futures_main_sina_hist = futures_main_sina(
        symbol="CF0", start_date="20240124", end_date="20240301"
    )
    print(futures_main_sina_hist)
