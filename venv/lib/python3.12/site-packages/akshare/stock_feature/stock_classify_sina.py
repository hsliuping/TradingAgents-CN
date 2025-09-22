#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/7/13 16:16
Desc: 新浪财经-股票-行业分类
http://vip.stock.finance.sina.com.cn/mkt/
"""

import math

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


def stock_classify_board() -> dict:
    """
    http://vip.stock.finance.sina.com.cn/mkt/
    :return: 股票分类字典
    :rtype: dict
    """
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes"
    r = requests.get(url)
    data_json = r.json()
    big_dict = {}
    class_name_list = [
        BeautifulSoup(item[0], "lxml").find("font").text
        if "font" in item[0]
        else item[0]
        for item in data_json[1][0][1]
    ]  # 沪深股市
    for num, class_name in enumerate(class_name_list):
        temp_df = pd.DataFrame([item for item in data_json[1][0][1][num][1:][0]])
        if temp_df.shape[1] == 5:
            temp_df.columns = ["name", "_", "code", "_", "_"]
            temp_df = temp_df[["name", "code"]]
        if temp_df.shape[1] == 4:
            temp_df.columns = ["name", "_", "code", "_"]
            temp_df = temp_df[["name", "code"]]
        if temp_df.shape[1] == 3:
            temp_df.columns = ["name", "_", "code"]
            temp_df = temp_df[["name", "code"]]
        big_dict.update({class_name: temp_df})
    return big_dict


def stock_classify_sina(symbol: str = "热门概念") -> pd.DataFrame:
    """
    按 symbol 分类后的股票
    http://vip.stock.finance.sina.com.cn/mkt/
    :param symbol: choice of {'申万行业', '申万二级', '热门概念', '地域板块'}
    :type symbol: str
    :return: 分类后的股票
    :rtype: pandas.DataFrame
    """
    stock_classify_board_dict = stock_classify_board()
    data_df = pd.DataFrame()
    for num in tqdm(range(len(stock_classify_board_dict[symbol]["code"])), leave=False):
        url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCount"
        params = {"node": stock_classify_board_dict[symbol]["code"][num]}
        r = requests.get(url, params=params)
        page_num = math.ceil(int(r.json()) / 80)
        url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
        big_df = pd.DataFrame()
        for page in range(1, page_num + 1):
            params = {
                "page": page,
                "num": "80",
                "sort": "symbol",
                "asc": "1",
                "node": stock_classify_board_dict[symbol]["code"][num],
                "symbol": "",
                "_s_r_a": "init",
            }
            r = requests.get(url, params=params)
            data_json = r.json()
            temp_df = pd.DataFrame(data_json)
            big_df = pd.concat([big_df, temp_df], ignore_index=True)
            big_df["class"] = stock_classify_board_dict[symbol]["name"][num]
        data_df = pd.concat([data_df, big_df], ignore_index=True)
    return data_df


if __name__ == "__main__":
    stock_classify_sina_df = stock_classify_sina(symbol="热门概念")
    print(stock_classify_sina_df)
