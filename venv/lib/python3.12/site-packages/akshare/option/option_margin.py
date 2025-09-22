#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/6/16 18:00
Desc: 唯爱期货-期权保证金
https://www.iweiai.com/qihuo/yuanyou
"""
import requests
import pandas as pd
from io import StringIO

from bs4 import BeautifulSoup
from functools import lru_cache


@lru_cache()
def option_margin_symbol() -> pd.DataFrame:
    """
    获取商品期权品种代码和名称
    :return: 商品期权品种代码和名称
    :rtype: pandas.DataFrame
    """
    url = "https://www.iweiai.com/qiquan/yuanyou"
    r = requests.get(url)
    soup = BeautifulSoup(r.content, features="lxml")
    symbol_text = [item.get_text() for item in soup.find_all("a") if "qiquan" in item['href']]
    symbol_url = [item['href'] for item in soup.find_all("a") if "qiquan" in item['href']]
    symbol_df = pd.DataFrame([symbol_text, symbol_url]).T
    symbol_df.columns = ["symbol", "url"]
    return symbol_df


def option_margin(symbol: str = "原油期权") -> pd.DataFrame:
    """
    获取商品期权保证金
    :param symbol: 商品期权品种名称, 如 "原油期权"，可以通过 ak.option_margin_symbol() 获取所有商品期权品种代码和名称
    :type symbol: str
    :return: 商品期权保证金
    :rtype: pandas.DataFrame
    """
    option_margin_symbol_df = option_margin_symbol()
    url = option_margin_symbol_df[option_margin_symbol_df['symbol'] == symbol]['url'].values[0]
    r = requests.get(url)
    soup = BeautifulSoup(r.content, features="lxml")
    updated_time = soup.find_all("small")[0].get_text().strip("最近更新：")
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df['更新时间'] = updated_time

    temp_df['结算价'] = pd.to_numeric(temp_df['结算价'], errors='coerce')
    temp_df['交易乘数'] = pd.to_numeric(temp_df['交易乘数'], errors='coerce')
    temp_df['买方权利金'] = pd.to_numeric(temp_df['买方权利金'], errors='coerce')
    temp_df['卖方保证金'] = pd.to_numeric(temp_df['卖方保证金'], errors='coerce')
    temp_df['开仓手续费'] = pd.to_numeric(temp_df['开仓手续费'], errors='coerce')
    temp_df['平今手续费'] = pd.to_numeric(temp_df['平今手续费'], errors='coerce')
    temp_df['平昨手续费'] = pd.to_numeric(temp_df['平昨手续费'], errors='coerce')
    temp_df['手续费(开+平今)'] = pd.to_numeric(temp_df['手续费(开+平今)'], errors='coerce')
    return temp_df


if __name__ == '__main__':
    option_margin_df = option_margin(symbol="原油期权")
    print(option_margin_df)
