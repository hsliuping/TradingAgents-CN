#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/4 20:00
Desc: 同花顺-财务指标-主要指标
https://basic.10jqka.com.cn/new/000063/finance.html
"""

import json

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.utils.cons import headers


def stock_financial_abstract_ths(
    symbol: str = "000063", indicator: str = "按报告期"
) -> pd.DataFrame:
    """
    同花顺-财务指标-主要指标
    https://basic.10jqka.com.cn/new/000063/finance.html
    :param symbol: 股票代码
    :type symbol: str
    :param indicator: 指标; choice of {"按报告期", "按年度", "按单季度"}
    :type indicator: str
    :return: 同花顺-财务指标-主要指标
    :rtype: pandas.DataFrame
    """
    url = f"https://basic.10jqka.com.cn/new/{symbol}/finance.html"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    data_text = soup.find(name="p", attrs={"id": "main"}).string
    data_json = json.loads(data_text)
    df_index = [
        item[0] if isinstance(item, list) else item for item in data_json["title"]
    ]
    if indicator == "按报告期":
        temp_df = pd.DataFrame(
            data_json["report"][1:], columns=data_json["report"][0], index=df_index[1:]
        )
    elif indicator == "按单季度":
        temp_df = pd.DataFrame(
            data_json["simple"][1:], columns=data_json["simple"][0], index=df_index[1:]
        )
    else:
        temp_df = pd.DataFrame(
            data_json["year"][1:], columns=data_json["year"][0], index=df_index[1:]
        )
    temp_df = temp_df.T
    temp_df.reset_index(inplace=True)
    temp_df.rename(columns={"index": "报告期"}, inplace=True)
    temp_df.sort_values(by="报告期", ignore_index=True, inplace=True)
    return temp_df


def stock_financial_debt_ths(
    symbol: str = "000063", indicator: str = "按报告期"
) -> pd.DataFrame:
    """
    同花顺-财务指标-资产负债表
    https://basic.10jqka.com.cn/new/000063/finance.html
    https://basic.10jqka.com.cn/api/stock/finance/000063_debt.json
    :param symbol: 股票代码
    :type symbol: str
    :param indicator: 指标; choice of {"按报告期", "按年度"}
    :type indicator: str
    :return: 同花顺-财务指标-资产负债表
    :rtype: pandas.DataFrame
    """
    url = f"https://basic.10jqka.com.cn/api/stock/finance/{symbol}_debt.json"
    r = requests.get(url, headers=headers)
    data_json = json.loads(json.loads(r.text)["flashData"])
    df_index = [
        item[0] if isinstance(item, list) else item for item in data_json["title"]
    ]
    if indicator == "按报告期":
        temp_df = pd.DataFrame(
            data_json["report"][1:], columns=data_json["report"][0], index=df_index[1:]
        )
    else:
        temp_df = pd.DataFrame(
            data_json["year"][1:], columns=data_json["year"][0], index=df_index[1:]
        )
    temp_df = temp_df.T
    temp_df.reset_index(inplace=True)
    temp_df.rename(columns={"index": "报告期"}, inplace=True)
    return temp_df


def stock_financial_benefit_ths(
    symbol: str = "000063", indicator: str = "按报告期"
) -> pd.DataFrame:
    """
    同花顺-财务指标-利润表
    https://basic.10jqka.com.cn/new/000063/finance.html
    https://basic.10jqka.com.cn/api/stock/finance/000063_benefit.json
    :param symbol: 股票代码
    :type symbol: str
    :param indicator: 指标; choice of {"按报告期","按单季度", "按年度"}
    :type indicator: str
    :return: 同花顺-财务指标-利润表
    :rtype: pandas.DataFrame
    """
    url = f"https://basic.10jqka.com.cn/api/stock/finance/{symbol}_benefit.json"
    r = requests.get(url, headers=headers)
    data_json = json.loads(json.loads(r.text)["flashData"])
    df_index = [
        item[0] if isinstance(item, list) else item for item in data_json["title"]
    ]
    if indicator == "按报告期":
        temp_df = pd.DataFrame(
            data_json["report"][1:], columns=data_json["report"][0], index=df_index[1:]
        )
    elif indicator == "按单季度":
        temp_df = pd.DataFrame(
            data_json["simple"][1:], columns=data_json["simple"][0], index=df_index[1:]
        )
    else:
        temp_df = pd.DataFrame(
            data_json["year"][1:], columns=data_json["year"][0], index=df_index[1:]
        )
    temp_df = temp_df.T
    temp_df.reset_index(inplace=True)
    temp_df.rename(columns={"index": "报告期"}, inplace=True)
    return temp_df


def stock_financial_cash_ths(
    symbol: str = "000063", indicator: str = "按报告期"
) -> pd.DataFrame:
    """
    同花顺-财务指标-现金流量表
    https://basic.10jqka.com.cn/new/000063/finance.html
    https://basic.10jqka.com.cn/api/stock/finance/000063_cash.json
    :param symbol: 股票代码
    :type symbol: str
    :param indicator: 指标; choice of {"按报告期","按单季度", "按年度"}
    :type indicator: str
    :return: 同花顺-财务指标-现金流量表
    :rtype: pandas.DataFrame
    """
    url = f"https://basic.10jqka.com.cn/api/stock/finance/{symbol}_cash.json"
    r = requests.get(url, headers=headers)
    data_json = json.loads(json.loads(r.text)["flashData"])
    df_index = [
        item[0] if isinstance(item, list) else item for item in data_json["title"]
    ]
    if indicator == "按报告期":
        temp_df = pd.DataFrame(
            data_json["report"][1:], columns=data_json["report"][0], index=df_index[1:]
        )
    elif indicator == "按单季度":
        temp_df = pd.DataFrame(
            data_json["simple"][1:], columns=data_json["simple"][0], index=df_index[1:]
        )
    else:
        temp_df = pd.DataFrame(
            data_json["year"][1:], columns=data_json["year"][0], index=df_index[1:]
        )
    temp_df = temp_df.T
    temp_df.reset_index(inplace=True)
    temp_df.rename(columns={"index": "报告期"}, inplace=True)
    return temp_df


def stock_management_change_ths(symbol: str = "688981") -> pd.DataFrame:
    """
    同花顺-公司大事-高管持股变动
    https://basic.10jqka.com.cn/new/688981/event.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 同花顺-公司大事-高管持股变动
    :rtype: pandas.DataFrame
    """
    url = f"https://basic.10jqka.com.cn/new/{symbol}/event.html"
    r = requests.get(url, headers=headers)
    r.encoding = "gb2312"
    soup = BeautifulSoup(r.text, features="lxml")
    soup_find = soup.find(name="table", attrs={"class": "data_table_1 m_table m_hl"})
    if soup_find is not None:
        content_list = [item.text.strip() for item in soup_find]
        column_names = content_list[1].split("\n")
        row = (
            content_list[3]
            .replace(" ", "")
            .replace("\t", "")
            .replace("\n\n", "")
            .replace("   ", "\n")
            .replace("\n\n", "\n")
            .split("\n")
        )
        row = [item for item in row if item != ""]
        new_rows = []
        step = len(column_names)
        for i in range(0, len(row), step):
            new_rows.append(row[i : i + step])
        temp_df = pd.DataFrame(new_rows, columns=column_names)
        temp_df.sort_values(by="变动日期", ignore_index=True, inplace=True)
        temp_df["变动日期"] = pd.to_datetime(
            temp_df["变动日期"], errors="coerce"
        ).dt.date
        temp_df.rename(
            columns={
                "变动数量（股）": "变动数量",
                "交易均价（元）": "交易均价",
                "剩余股数（股）": "剩余股数",
            },
            inplace=True,
        )
        return temp_df
    return pd.DataFrame()


def stock_shareholder_change_ths(symbol: str = "688981") -> pd.DataFrame:
    """
    同花顺-公司大事-股东持股变动
    https://basic.10jqka.com.cn/new/688981/event.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 同花顺-公司大事-股东持股变动
    :rtype: pandas.DataFrame
    """
    url = f"https://basic.10jqka.com.cn/new/{symbol}/event.html"
    r = requests.get(url, headers=headers)
    r.encoding = "gb2312"
    soup = BeautifulSoup(r.text, features="lxml")
    soup_find = soup.find(name="table", attrs={"class": "m_table data_table_1 m_hl"})
    if soup_find is not None:
        content_list = [item.text.strip() for item in soup_find]
        column_names = content_list[1].split("\n")
        row = (
            content_list[3]
            .replace("\t", "")
            .replace("\n\n", "")
            .replace("   ", "\n")
            .replace(" ", "")
            .replace("\n\n", "\n")
            .split("\n")
        )
        row = [item for item in row if item != ""]
        new_rows = []
        step = len(column_names)
        for i in range(0, len(row), step):
            new_rows.append(row[i : i + step])
        temp_df = pd.DataFrame(new_rows, columns=column_names)
        temp_df.sort_values(by="公告日期", ignore_index=True, inplace=True)
        temp_df["公告日期"] = pd.to_datetime(
            temp_df["公告日期"], errors="coerce"
        ).dt.date
        temp_df.rename(
            columns={
                "变动数量(股)": "变动数量",
                "交易均价(元)": "交易均价",
                "剩余股份总数(股)": "剩余股份总数",
            },
            inplace=True,
        )
        return temp_df
    return pd.DataFrame()


if __name__ == "__main__":
    stock_financial_abstract_ths_df = stock_financial_abstract_ths(
        symbol="000063", indicator="按报告期"
    )
    print(stock_financial_abstract_ths_df)

    stock_financial_abstract_ths_df = stock_financial_abstract_ths(
        symbol="000063", indicator="按年度"
    )
    print(stock_financial_abstract_ths_df)

    stock_financial_abstract_ths_df = stock_financial_abstract_ths(
        symbol="000063", indicator="按单季度"
    )
    print(stock_financial_abstract_ths_df)

    stock_financial_debt_ths_df = stock_financial_debt_ths(
        symbol="002004", indicator="按报告期"
    )
    print(stock_financial_debt_ths_df)

    stock_financial_debt_ths_df = stock_financial_debt_ths(
        symbol="000063", indicator="按年度"
    )
    print(stock_financial_debt_ths_df)

    stock_financial_benefit_ths_df = stock_financial_benefit_ths(
        symbol="000063", indicator="按报告期"
    )
    print(stock_financial_benefit_ths_df)

    stock_financial_benefit_ths_df = stock_financial_benefit_ths(
        symbol="000063", indicator="按年度"
    )
    print(stock_financial_benefit_ths_df)

    stock_financial_benefit_ths_df = stock_financial_benefit_ths(
        symbol="000063", indicator="按报告期"
    )
    print(stock_financial_benefit_ths_df)

    stock_financial_cash_ths_df = stock_financial_cash_ths(
        symbol="000063", indicator="按年度"
    )
    print(stock_financial_cash_ths_df)

    stock_financial_cash_ths_df = stock_financial_cash_ths(
        symbol="000063", indicator="按年度"
    )
    print(stock_financial_cash_ths_df)

    stock_financial_cash_ths_df = stock_financial_cash_ths(
        symbol="000063", indicator="按单季度"
    )
    print(stock_financial_cash_ths_df)

    stock_management_change_ths_df = stock_management_change_ths(symbol="688981")
    print(stock_management_change_ths_df)

    stock_shareholder_change_ths_df = stock_shareholder_change_ths(symbol="688981")
    print(stock_shareholder_change_ths_df)
