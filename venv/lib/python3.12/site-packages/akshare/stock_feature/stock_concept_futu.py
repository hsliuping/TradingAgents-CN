#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/7/16 22:00
Desc: 富途牛牛-主题投资-概念板块-成分股
https://www.futunn.com/quote/sparks-us
"""

import json

import pandas as pd
import requests
from bs4 import BeautifulSoup


def _stock_concept_cons_futu(symbol: str = "巴菲特持仓") -> pd.DataFrame:
    """
    富途牛牛-主题投资-概念板块-成分股
    https://www.futunn.com/quote/sparks-us
    :param symbol: 板块名称; choice of {"巴菲特持仓", "佩洛西持仓"}
    :type symbol: str
    :return: 概念板块
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "巴菲特持仓": "BK2999",
        "佩洛西持仓": "BK20883",
    }
    url = f"https://www.futunn.com/stock/{symbol_map[symbol]}"
    # 定义查询参数
    params = {"global_content": json.dumps({"promote_id": 13766, "sub_promote_id": 24})}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    temp_code_name = [
        item.find_all("div", attrs={"class": "fix-left"})
        for item in soup.find(name="div", attrs={"class": "content-main"}).find_all("a")
    ]
    temp_value_list = [
        item.find_all("div", attrs={"class": "middle"})
        for item in soup.find(name="div", attrs={"class": "content-main"}).find_all("a")
    ]
    code_name_list = [item[0].find_all("span") for item in temp_code_name]

    quant_list = [item[0].find_all("span") for item in temp_value_list]
    temp_df = pd.DataFrame(
        [
            [item[0]["title"] for item in code_name_list],
            [item[1]["title"] for item in code_name_list],
            [item[0]["title"] for item in quant_list],
            [item[1]["title"] for item in quant_list],
            [item[2]["title"] for item in quant_list],
            [item[3]["title"] for item in quant_list],
            [item[4]["title"] for item in quant_list],
            [item[5]["title"] for item in quant_list],
            [item[6]["title"] for item in quant_list],
            [item[7]["title"] for item in quant_list],
            [item[8]["title"] for item in quant_list],
            [item[9]["title"] for item in quant_list],
            [item[10]["title"] for item in quant_list],
            [item[11]["title"] for item in quant_list],
            [item[12]["title"] for item in quant_list],
            [item[13]["title"] for item in quant_list],
            [item[14]["title"] for item in quant_list],
        ]
    ).T
    temp_df.columns = [
        "代码",
        "股票名称",
        "最新价",
        "涨跌额",
        "涨跌幅",
        "成交量",
        "成交额",
        "-",
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
    temp_df = temp_df[
        [
            "代码",
            "股票名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "成交量",
            "成交额",
        ]
    ]
    return temp_df


def stock_concept_cons_futu(symbol: str = "特朗普概念股") -> pd.DataFrame:
    """
    富途牛牛-主题投资-概念板块-成分股
    https://www.futunn.com/quote/sparks-us
    :param symbol: 板块名称; choice of {"巴菲特持仓", "佩洛西持仓", "特朗普概念股"}
    :type symbol: str
    :return: 概念板块
    :rtype: pandas.DataFrame
    """
    if symbol == "特朗普概念股":
        url = "https://www.futunn.com/quote-api/quote-v2/get-plate-stock"
        params = {
            "marketType": "2",
            "plateId": "10102960",
            "page": "0",
            "pageSize": "30",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Quote-Token": "7f74cd2a5e",
        }
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        total_page = data_json["data"]["pagination"]["pageCount"]
        big_df = pd.DataFrame()
        for page in range(0, total_page):
            params.update(
                {
                    "page": page,
                }
            )
            if page == 1:
                headers.update({"Quote-Token": "a3043d6fed"})
            r = requests.get(url, params=params, headers=headers)
            data_json = r.json()
            temp_df = pd.DataFrame(data_json["data"]["list"])
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

        big_df.rename(
            columns={
                "stockCode": "代码",
                "name": "股票名称",
                "price": "最新价",
                "change": "涨跌额",
                "changeRatio": "涨跌幅",
                "tradeVolumn": "成交量",
                "tradeTrunover": "成交额",
            },
            inplace=True,
        )
        big_df = big_df[
            [
                "代码",
                "股票名称",
                "最新价",
                "涨跌额",
                "涨跌幅",
                "成交量",
                "成交额",
            ]
        ]
        big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
        big_df["涨跌额"] = pd.to_numeric(big_df["涨跌额"], errors="coerce")
        return big_df
    else:
        temp_df = _stock_concept_cons_futu(symbol)
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
        return temp_df


if __name__ == "__main__":
    stock_concept_cons_futu_df = stock_concept_cons_futu(symbol="特朗普概念股")
    print(stock_concept_cons_futu_df)

    stock_concept_cons_futu_df = stock_concept_cons_futu(symbol="巴菲特持仓")
    print(stock_concept_cons_futu_df)

    stock_concept_cons_futu_df = stock_concept_cons_futu(symbol="佩洛西持仓")
    print(stock_concept_cons_futu_df)
