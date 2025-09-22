#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/1/23 10:21
Desc: 新浪财经-商品期权
https://stock.finance.sina.com.cn/futures/view/optionsDP.php
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.utils import demjson


def option_commodity_contract_sina(symbol: str = "玉米期权") -> pd.DataFrame:
    """
    当前可以查询的期权品种的合约日期
    https://stock.finance.sina.com.cn/futures/view/optionsDP.php
    :param symbol: choice of {"豆粕期权", "玉米期权", "铁矿石期权", "棉花期权", "白糖期权", "PTA期权", "甲醇期权", "橡胶期权", "沪铜期权", "黄金期权", "菜籽粕期权", "液化石油气期权", "动力煤期权", "菜籽油期权", "花生期权"}
    :type symbol: str
    :return: e.g., {'黄金期权': ['au2012', 'au2008', 'au2010', 'au2104', 'au2102', 'au2106', 'au2108']}
    :rtype: dict
    """
    url = "https://stock.finance.sina.com.cn/futures/view/optionsDP.php/pg_o/dce"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    url_list = [
        item.find("a")["href"]
        for item in soup.find_all("li", attrs={"class": "active"})
        if item.find("a") is not None
    ]
    commodity_list = [
        item.find("a").text
        for item in soup.find_all("li", attrs={"class": "active"})
        if item.find("a") is not None
    ]
    comm_list_dict = {key: value for key, value in zip(commodity_list, url_list)}
    url = "https://stock.finance.sina.com.cn" + comm_list_dict[symbol]
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    symbol = (
        soup.find(attrs={"id": "option_symbol"}).find(attrs={"class": "selected"}).text
    )
    contract = [
        item.text for item in soup.find(attrs={"id": "option_suffix"}).find_all("li")
    ]
    temp_df = pd.DataFrame({symbol: contract})
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1
    temp_df.columns = ["序号", "合约"]
    return temp_df


def option_commodity_contract_table_sina(
    symbol: str = "黄金期权", contract: str = "au2204"
) -> pd.DataFrame:
    """
    当前所有期权合约, 包括看涨期权合约和看跌期权合约
    https://stock.finance.sina.com.cn/futures/view/optionsDP.php
    :param symbol: choice of {"豆粕期权", "玉米期权", "铁矿石期权", "棉花期权", "白糖期权", "PTA期权", "甲醇期权", "橡胶期权", "沪铜期权", "黄金期权", "菜籽粕期权", "液化石油气期权", "动力煤期权", "菜籽油期权", "花生期权"}
    :type symbol: str
    :param contract: e.g., 'au2012'
    :type contract: str
    :return: 合约实时行情
    :rtype: pandas.DataFrame
    """
    url = "https://stock.finance.sina.com.cn/futures/view/optionsDP.php/pg_o/dce"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    url_list = [
        item.find("a")["href"]
        for item in soup.find_all("li", attrs={"class": "active"})
        if item.find("a") is not None
    ]
    commodity_list = [
        item.find("a").text
        for item in soup.find_all("li", attrs={"class": "active"})
        if item.find("a") is not None
    ]
    comm_list_dict = {key: value for key, value in zip(commodity_list, url_list)}
    url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/OptionService.getOptionData"
    params = {
        "type": "futures",
        "product": comm_list_dict[symbol].split("/")[-2],
        "exchange": comm_list_dict[symbol].split("/")[-1],
        "pinzhong": contract,
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    up_df = pd.DataFrame(data_json["result"]["data"]["up"])
    down_df = pd.DataFrame(data_json["result"]["data"]["down"])
    temp_df = pd.concat([up_df, down_df], axis=1)
    temp_df.columns = [
        "看涨合约-买量",
        "看涨合约-买价",
        "看涨合约-最新价",
        "看涨合约-卖价",
        "看涨合约-卖量",
        "看涨合约-持仓量",
        "看涨合约-涨跌",
        "行权价",
        "看涨合约-看涨期权合约",
        "看跌合约-买量",
        "看跌合约-买价",
        "看跌合约-最新价",
        "看跌合约-卖价",
        "看跌合约-卖量",
        "看跌合约-持仓量",
        "看跌合约-涨跌",
        "看跌合约-看跌期权合约",
    ]
    temp_df["看涨合约-买量"] = pd.to_numeric(temp_df["看涨合约-买量"], errors="coerce")
    temp_df["看涨合约-买价"] = pd.to_numeric(temp_df["看涨合约-买价"], errors="coerce")
    temp_df["看涨合约-最新价"] = pd.to_numeric(
        temp_df["看涨合约-最新价"], errors="coerce"
    )
    temp_df["看涨合约-卖价"] = pd.to_numeric(temp_df["看涨合约-卖价"], errors="coerce")
    temp_df["看涨合约-卖量"] = pd.to_numeric(temp_df["看涨合约-卖量"], errors="coerce")
    temp_df["看涨合约-持仓量"] = pd.to_numeric(
        temp_df["看涨合约-持仓量"], errors="coerce"
    )
    temp_df["看涨合约-涨跌"] = pd.to_numeric(temp_df["看涨合约-涨跌"], errors="coerce")
    temp_df["行权价"] = pd.to_numeric(temp_df["行权价"], errors="coerce")
    temp_df["看跌合约-买量"] = pd.to_numeric(temp_df["看跌合约-买量"], errors="coerce")
    temp_df["看跌合约-买价"] = pd.to_numeric(temp_df["看跌合约-买价"], errors="coerce")
    temp_df["看跌合约-最新价"] = pd.to_numeric(
        temp_df["看跌合约-最新价"], errors="coerce"
    )
    temp_df["看跌合约-卖价"] = pd.to_numeric(temp_df["看跌合约-卖价"], errors="coerce")
    temp_df["看跌合约-卖量"] = pd.to_numeric(temp_df["看跌合约-卖量"], errors="coerce")
    temp_df["看跌合约-持仓量"] = pd.to_numeric(
        temp_df["看跌合约-持仓量"], errors="coerce"
    )
    temp_df["看跌合约-涨跌"] = pd.to_numeric(temp_df["看跌合约-涨跌"], errors="coerce")
    return temp_df


def option_commodity_hist_sina(symbol: str = "au2012C392") -> pd.DataFrame:
    """
    合约历史行情-日频
    https://stock.finance.sina.com.cn/futures/view/optionsDP.php
    :param symbol: return of option_sina_option_commodity_contract_list(symbol="黄金期权", contract="au2012"), 看涨期权合约 filed
    :type symbol: str
    :return: 合约历史行情-日频
    :rtype: pandas.DataFrame
    """
    url = "https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20_m2009C30002020_7_17=/FutureOptionAllService.getOptionDayline"
    params = {"symbol": symbol}
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("[") : -2])
    temp_df = pd.DataFrame(data_json)
    temp_df.columns = ["open", "high", "low", "close", "volume", "date"]
    temp_df = temp_df[["date", "open", "high", "low", "close", "volume"]]
    temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
    temp_df["open"] = pd.to_numeric(temp_df["open"])
    temp_df["high"] = pd.to_numeric(temp_df["high"])
    temp_df["low"] = pd.to_numeric(temp_df["low"])
    temp_df["close"] = pd.to_numeric(temp_df["close"])
    temp_df["volume"] = pd.to_numeric(temp_df["volume"])
    return temp_df


if __name__ == "__main__":
    option_commodity_contract_sina_df = option_commodity_contract_sina(
        symbol="棉花期权"
    )
    print(option_commodity_contract_sina_df)

    option_commodity_contract_table_sina_df = option_commodity_contract_table_sina(
        symbol="棉花期权", contract="cf2301"
    )
    print(option_commodity_contract_table_sina_df)

    option_commodity_hist_sina_df = option_commodity_hist_sina(symbol="cf2301P21600")
    print(option_commodity_hist_sina_df)
