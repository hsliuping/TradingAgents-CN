#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/8/3 20:00
Desc: 乘联会
http://data.cpcadata.com/FuelMarket
"""

import pandas as pd
import requests


def car_market_total_cpca(
    symbol: str = "狭义乘用车", indicator: str = "产量"
) -> pd.DataFrame:
    """
    乘联会-统计数据-总体市场
    http://data.cpcadata.com/TotalMarket
    :param symbol: choice of {"狭义乘用车", "广义乘用车"}
    :type symbol: str
    :param indicator: choice of {"产量", "批发", "零售", "出口"}
    :type indicator: str
    :return: 统计数据-总体市场
    :rtype: pandas.DataFrame
    """
    url = "http://data.cpcadata.com/api/chartlist"
    params = {"charttype": "1"}
    r = requests.get(url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    if symbol == "狭义乘用车":
        temp_df = pd.DataFrame(data_json[0]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[0]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        if indicator == "产量":
            big_df = pd.DataFrame(
                [temp_current_year_df.iloc[:, 0], temp_previous_year_df.iloc[:, 0]]
            ).T
            big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
            big_df["月份"] = temp_df["month"]
            big_df = big_df[
                [
                    "月份",
                    temp_df.columns[2],
                    temp_df.columns[1],
                ]
            ]
        elif indicator == "批发":
            big_df = pd.DataFrame(
                [temp_current_year_df.iloc[:, 1], temp_previous_year_df.iloc[:, 1]]
            ).T
            big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
            big_df["月份"] = temp_df["month"]
            big_df = big_df[
                [
                    "月份",
                    temp_df.columns[2],
                    temp_df.columns[1],
                ]
            ]
        elif indicator == "零售":
            big_df = pd.DataFrame(
                [temp_current_year_df.iloc[:, 2], temp_previous_year_df.iloc[:, 2]]
            ).T
            big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
            big_df["月份"] = temp_df["month"]
            big_df = big_df[
                [
                    "月份",
                    temp_df.columns[2],
                    temp_df.columns[1],
                ]
            ]
        elif indicator == "出口":
            big_df = pd.DataFrame(
                [temp_current_year_df.iloc[:, 3], temp_previous_year_df.iloc[:, 3]]
            ).T
            big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
            big_df["月份"] = temp_df["month"]
            big_df = big_df[
                [
                    "月份",
                    temp_df.columns[2],
                    temp_df.columns[1],
                ]
            ]
    else:
        temp_df = pd.DataFrame(data_json[1]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[1]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        if indicator == "产量":
            big_df = pd.DataFrame(
                [temp_current_year_df.iloc[:, 0], temp_previous_year_df.iloc[:, 0]]
            ).T
            big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
            big_df["月份"] = temp_df["month"]
            big_df = big_df[
                [
                    "月份",
                    temp_df.columns[2],
                    temp_df.columns[1],
                ]
            ]
        elif indicator == "批发":
            big_df = pd.DataFrame(
                [temp_current_year_df.iloc[:, 1], temp_previous_year_df.iloc[:, 1]]
            ).T
            big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
            big_df["月份"] = temp_df["month"]
            big_df = big_df[
                [
                    "月份",
                    temp_df.columns[2],
                    temp_df.columns[1],
                ]
            ]
        elif indicator == "零售":
            big_df = pd.DataFrame(
                [temp_current_year_df.iloc[:, 2], temp_previous_year_df.iloc[:, 2]]
            ).T
            big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
            big_df["月份"] = temp_df["month"]
            big_df = big_df[
                [
                    "月份",
                    temp_df.columns[2],
                    temp_df.columns[1],
                ]
            ]
        elif indicator == "出口":
            big_df = pd.DataFrame(
                [temp_current_year_df.iloc[:, 3], temp_previous_year_df.iloc[:, 3]]
            ).T
            big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
            big_df["月份"] = temp_df["month"]
            big_df = big_df[
                [
                    "月份",
                    temp_df.columns[2],
                    temp_df.columns[1],
                ]
            ]

    return big_df


def __car_market_man_rank_cpca_pifa(symbol: str = "狭义乘用车-累计") -> pd.DataFrame:
    """
    乘联会-统计数据-厂商排名
    http://data.cpcadata.com/ManRank
    :param symbol: choice of {"狭义乘用车-单月", "狭义乘用车-累计", "广义乘用车-单月", "广义乘用车-累计"}
    :type symbol: str
    :return: 统计数据-厂商排名
    :rtype: pandas.DataFrame
    """
    url = "http://data.cpcadata.com/api/chartlist"
    params = {"charttype": "2"}
    r = requests.get(url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    if symbol == "狭义乘用车-累计":
        temp_df = pd.DataFrame(data_json[0]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[0]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 0], temp_previous_year_df.iloc[:, 0]]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
        big_df["厂商"] = temp_df["厂商"]
        big_df = big_df[
            [
                "厂商",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "狭义乘用车-单月":
        temp_df = pd.DataFrame(data_json[1]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[1]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 0], temp_previous_year_df.iloc[:, 0]]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
        big_df["厂商"] = temp_df["厂商"]
        big_df = big_df[
            [
                "厂商",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "广义乘用车-累计":
        temp_df = pd.DataFrame(data_json[2]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[2]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 0], temp_previous_year_df.iloc[:, 0]]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
        big_df["厂商"] = temp_df["厂商"]
        big_df = big_df[
            [
                "厂商",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "广义乘用车-单月":
        temp_df = pd.DataFrame(data_json[3]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[3]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 0], temp_previous_year_df.iloc[:, 0]]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
        big_df["厂商"] = temp_df["厂商"]
        big_df = big_df[
            [
                "厂商",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    return big_df


def __car_market_man_rank_cpca_lingshou(
    symbol: str = "狭义乘用车-累计",
) -> pd.DataFrame:
    """
    乘联会-统计数据-厂商排名
    http://data.cpcadata.com/ManRank
    :param symbol: choice of {"狭义乘用车-单月", "狭义乘用车-累计", "广义乘用车-单月", "广义乘用车-累计"}
    :type symbol: str
    :return: 统计数据-厂商排名
    :rtype: pandas.DataFrame
    """
    url = "http://data.cpcadata.com/api/chartlist_2"
    params = {"charttype": "2"}
    r = requests.get(url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    if symbol == "狭义乘用车-累计":
        temp_df = pd.DataFrame(data_json[0]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[0]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 1], temp_previous_year_df.iloc[:, 1]]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
        big_df["厂商"] = temp_df["厂商"]
        big_df = big_df[
            [
                "厂商",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "狭义乘用车-单月":
        temp_df = pd.DataFrame(data_json[1]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[1]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 1], temp_previous_year_df.iloc[:, 1]]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
        big_df["厂商"] = temp_df["厂商"]
        big_df = big_df[
            [
                "厂商",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "广义乘用车-累计":
        temp_df = pd.DataFrame(data_json[2]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[2]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 1], temp_previous_year_df.iloc[:, 1]]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
        big_df["厂商"] = temp_df["厂商"]
        big_df = big_df[
            [
                "厂商",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "广义乘用车-单月":
        temp_df = pd.DataFrame(data_json[3]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[3]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 1], temp_previous_year_df.iloc[:, 1]]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
        big_df["厂商"] = temp_df["厂商"]
        big_df = big_df[
            [
                "厂商",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    return big_df


def car_market_man_rank_cpca(
    symbol: str = "狭义乘用车-单月", indicator: str = "批发"
) -> pd.DataFrame:
    """
    乘联会-统计数据-厂商排名
    http://data.cpcadata.com/ManRank
    :param symbol: choice of {"狭义乘用车-单月", "狭义乘用车-累计", "广义乘用车-单月", "广义乘用车-累计"}
    :type symbol: str
    :param indicator: choice of {"批发", "零售"}
    :type indicator: str
    :return: 统计数据-厂商排名
    :rtype: pandas.DataFrame
    """
    if indicator == "批发":
        temp_df = __car_market_man_rank_cpca_pifa(symbol=symbol)
        return temp_df
    else:
        temp_df = __car_market_man_rank_cpca_lingshou(symbol=symbol)
        return temp_df


def __car_market_cate_cpca_pifa(symbol: str = "MPV") -> pd.DataFrame:
    """
    乘联会-统计数据-车型大类
    http://data.cpcadata.com/CategoryMarket
    :param symbol: choice of {"轿车", "MPV", "SUV", "占比"}
    :type symbol: str
    :return: 统计数据-车型大类
    :rtype: pandas.DataFrame
    """
    url = "http://data.cpcadata.com/api/chartlist"
    params = {"charttype": "3"}
    r = requests.get(url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    if symbol == "MPV":
        temp_df = pd.DataFrame(data_json[0]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[0]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[1]])
            try:
                temp_current_year_list.append(item[temp_df.columns[2]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 1], temp_previous_year_df.iloc[:, 1]]
        ).T
        big_df.columns = [temp_df.columns[2], temp_df.columns[1]]
        big_df["月份"] = temp_df["month"]
        big_df = big_df[
            [
                "月份",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "SUV":
        temp_df = pd.DataFrame(data_json[1]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[1]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[1]])
            try:
                temp_current_year_list.append(item[temp_df.columns[2]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 1], temp_previous_year_df.iloc[:, 1]]
        ).T
        big_df.columns = [temp_df.columns[2], temp_df.columns[1]]
        big_df["月份"] = temp_df["month"]
        big_df = big_df[
            [
                "月份",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "轿车":
        temp_df = pd.DataFrame(data_json[2]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[2]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[1]])
            try:
                temp_current_year_list.append(item[temp_df.columns[2]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 1], temp_previous_year_df.iloc[:, 1]]
        ).T
        big_df.columns = [temp_df.columns[2], temp_df.columns[1]]
        big_df["月份"] = temp_df["month"]
        big_df = big_df[
            [
                "月份",
                temp_df.columns[1],
                temp_df.columns[2],
            ]
        ]
    elif symbol == "占比":
        temp_df = pd.DataFrame(data_json[3]["dataList"])
        temp_mpv_year_list = []
        temp_suv_year_list = []
        temp_jiaoche_year_list = []
        for item in data_json[3]["dataList"]:
            temp_mpv_year_list.append(item[temp_df.columns[1]])
            try:
                temp_suv_year_list.append(item[temp_df.columns[2]])
                temp_jiaoche_year_list.append(item[temp_df.columns[3]])
            except:  # noqa: E722
                continue
        temp_mpv_year_df = pd.DataFrame(temp_mpv_year_list)
        temp_suv_year_df = pd.DataFrame(temp_suv_year_list)
        temp_jiaoche_year_df = pd.DataFrame(temp_jiaoche_year_list)
        big_df = pd.DataFrame(
            [
                temp_mpv_year_df.iloc[:, 2],
                temp_suv_year_df.iloc[:, 2],
                temp_jiaoche_year_df.iloc[:, 2],
            ]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2], temp_df.columns[3]]
        big_df["月份"] = temp_df["月份"]
        big_df = big_df[
            ["月份", temp_df.columns[1], temp_df.columns[2], temp_df.columns[3]]
        ]
    return big_df


def __car_market_cate_cpca_lingshou(
    symbol: str = "狭义乘用车-累计",
) -> pd.DataFrame:
    """
    乘联会-统计数据-车型大类
    http://data.cpcadata.com/CategoryMarket
    :param symbol: choice of {"轿车", "MPV", "SUV", "占比"}
    :type symbol: str
    :return: 统计数据-车型大类
    :rtype: pandas.DataFrame
    """
    url = "http://data.cpcadata.com/api/chartlist"
    params = {"charttype": "3"}
    r = requests.get(url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    if symbol == "MPV":
        temp_df = pd.DataFrame(data_json[0]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[0]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[1]])
            try:
                temp_current_year_list.append(item[temp_df.columns[2]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 2], temp_previous_year_df.iloc[:, 2]]
        ).T
        big_df.columns = [temp_df.columns[2], temp_df.columns[1]]
        big_df["月份"] = temp_df["month"]
        big_df = big_df[
            [
                "月份",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "SUV":
        temp_df = pd.DataFrame(data_json[1]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[1]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[1]])
            try:
                temp_current_year_list.append(item[temp_df.columns[2]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 2], temp_previous_year_df.iloc[:, 2]]
        ).T
        big_df.columns = [temp_df.columns[2], temp_df.columns[1]]
        big_df["月份"] = temp_df["month"]
        big_df = big_df[
            [
                "月份",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "轿车":
        temp_df = pd.DataFrame(data_json[2]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[2]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[1]])
            try:
                temp_current_year_list.append(item[temp_df.columns[2]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 2], temp_previous_year_df.iloc[:, 2]]
        ).T
        big_df.columns = [temp_df.columns[2], temp_df.columns[1]]
        big_df["月份"] = temp_df["month"]
        big_df = big_df[
            [
                "月份",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "占比":
        temp_df = pd.DataFrame(data_json[3]["dataList"])
        temp_mpv_year_list = []
        temp_suv_year_list = []
        temp_jiaoche_year_list = []
        for item in data_json[3]["dataList"]:
            temp_mpv_year_list.append(item[temp_df.columns[1]])
            try:
                temp_suv_year_list.append(item[temp_df.columns[2]])
                temp_jiaoche_year_list.append(item[temp_df.columns[3]])
            except:  # noqa: E722
                continue
        temp_mpv_year_df = pd.DataFrame(temp_mpv_year_list)
        temp_suv_year_df = pd.DataFrame(temp_suv_year_list)
        temp_jiaoche_year_df = pd.DataFrame(temp_jiaoche_year_list)
        big_df = pd.DataFrame(
            [
                temp_mpv_year_df.iloc[:, 3],
                temp_suv_year_df.iloc[:, 3],
                temp_jiaoche_year_df.iloc[:, 3],
            ]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2], temp_df.columns[3]]
        big_df["月份"] = temp_df["月份"]
        big_df = big_df[
            ["月份", temp_df.columns[1], temp_df.columns[2], temp_df.columns[3]]
        ]
    return big_df


def car_market_cate_cpca(symbol: str = "轿车", indicator: str = "批发") -> pd.DataFrame:
    """
    乘联会-统计数据-车型大类
    http://data.cpcadata.com/CategoryMarket
    :param symbol: choice of {"轿车", "MPV", "SUV", "占比"}
    :type symbol: str
    :param indicator: choice of {"批发", "零售"}
    :type indicator: str
    :return: 统计数据-车型大类
    :rtype: pandas.DataFrame
    """
    if indicator == "批发":
        temp_df = __car_market_cate_cpca_pifa(symbol=symbol)
        return temp_df
    else:
        temp_df = __car_market_cate_cpca_lingshou(symbol=symbol)
        return temp_df


def car_market_country_cpca() -> pd.DataFrame:
    """
    乘联会-统计数据-国别细分市场
    http://data.cpcadata.com/CountryMarket
    :return: 统计数据-车型大类
    :rtype: pandas.DataFrame
    """
    url = "http://data.cpcadata.com/api/chartlist"
    params = {"charttype": "4"}
    r = requests.get(url=url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json[0]["dataList"])
    for item in temp_df.columns[1:]:
        temp_list = []
        for item_list in temp_df[item]:
            temp_list.append(item_list[2])
        temp_df[item] = pd.to_numeric(temp_list, errors="coerce")
    return temp_df


def car_market_segment_cpca(symbol: str = "轿车") -> pd.DataFrame:
    """
    乘联会-统计数据-级别细分市场
    http://data.cpcadata.com/SegmentMarket
    :param symbol: choice of {"轿车", "MPV", "SUV"}
    :type symbol: str
    :return: 统计数据-车型大类
    :rtype: pandas.DataFrame
    """
    url = "http://data.cpcadata.com/api/chartlist"
    params = {"charttype": "5"}
    r = requests.get(url=url, params=params)
    data_json = r.json()
    if symbol == "MPV":
        temp_df = pd.DataFrame(data_json[0]["dataList"])
        for item in temp_df.columns[1:]:
            temp_list = []
            for item_list in temp_df[item]:
                temp_list.append(item_list[2])
            temp_df[item] = pd.to_numeric(temp_list, errors="coerce")
    elif symbol == "SUV":
        temp_df = pd.DataFrame(data_json[1]["dataList"])
        for item in temp_df.columns[1:]:
            temp_list = []
            for item_list in temp_df[item]:
                temp_list.append(item_list[2])
            temp_df[item] = pd.to_numeric(temp_list, errors="coerce")
    else:
        temp_df = pd.DataFrame(data_json[2]["dataList"])
        for item in temp_df.columns[1:]:
            temp_list = []
            for item_list in temp_df[item]:
                temp_list.append(item_list[2])
            temp_df[item] = pd.to_numeric(temp_list, errors="coerce")
    return temp_df


def car_market_fuel_cpca(symbol: str = "整体市场") -> pd.DataFrame:
    """
    乘联会-统计数据-新能源细分市场
    :param symbol: choice of {"整体市场", "销量占比-PHEV-BEV", "销量占比-ICE-NEV"}
    :type symbol: str
    https://data.cpcadata.com/FuelMarket
    :return: 新能源细分市场
    :rtype: pandas.DataFrame
    """
    url = "http://data.cpcadata.com/api/chartlist"
    params = {"charttype": "6"}
    r = requests.get(url, params=params)
    data_json = r.json()
    if symbol == "整体市场":
        temp_df = pd.DataFrame(data_json[0]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[0]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 2], temp_previous_year_df.iloc[:, 2]]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
        big_df["月份"] = temp_df["month"]
        big_df = big_df[
            [
                "月份",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    elif symbol == "销量占比-PHEV-BEV":
        temp_df = pd.DataFrame(data_json[1]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[1]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 2], temp_previous_year_df.iloc[:, 2]]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
        big_df["月份"] = temp_df["月份"]
        big_df = big_df[
            [
                "月份",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    else:
        temp_df = pd.DataFrame(data_json[2]["dataList"])
        temp_current_year_list = []
        temp_previous_year_list = []
        for item in data_json[2]["dataList"]:
            temp_previous_year_list.append(item[temp_df.columns[2]])
            try:
                temp_current_year_list.append(item[temp_df.columns[1]])
            except:  # noqa: E722
                continue
        temp_current_year_df = pd.DataFrame(temp_current_year_list)
        temp_previous_year_df = pd.DataFrame(temp_previous_year_list)
        big_df = pd.DataFrame(
            [temp_current_year_df.iloc[:, 2], temp_previous_year_df.iloc[:, 2]]
        ).T
        big_df.columns = [temp_df.columns[1], temp_df.columns[2]]
        big_df["月份"] = temp_df["月份"]
        big_df = big_df[
            [
                "月份",
                temp_df.columns[2],
                temp_df.columns[1],
            ]
        ]
    return big_df


if __name__ == "__main__":
    car_market_total_cpca_df = car_market_total_cpca(
        symbol="狭义乘用车", indicator="产量"
    )
    print(car_market_total_cpca_df)

    car_market_total_cpca_df = car_market_total_cpca(
        symbol="广义乘用车", indicator="产量"
    )
    print(car_market_total_cpca_df)

    car_market_total_cpca_df = car_market_total_cpca(
        symbol="狭义乘用车", indicator="批发"
    )
    print(car_market_total_cpca_df)

    car_market_total_cpca_df = car_market_total_cpca(
        symbol="广义乘用车", indicator="批发"
    )
    print(car_market_total_cpca_df)

    car_market_total_cpca_df = car_market_total_cpca(
        symbol="狭义乘用车", indicator="零售"
    )
    print(car_market_total_cpca_df)

    car_market_total_cpca_df = car_market_total_cpca(
        symbol="广义乘用车", indicator="零售"
    )
    print(car_market_total_cpca_df)

    car_market_total_cpca_df = car_market_total_cpca(
        symbol="狭义乘用车", indicator="出口"
    )
    print(car_market_total_cpca_df)

    car_market_total_cpca_df = car_market_total_cpca(
        symbol="广义乘用车", indicator="出口"
    )
    print(car_market_total_cpca_df)

    car_market_man_rank_cpca_df = car_market_man_rank_cpca(
        symbol="狭义乘用车-单月", indicator="批发"
    )
    print(car_market_man_rank_cpca_df)

    car_market_man_rank_cpca_df = car_market_man_rank_cpca(
        symbol="狭义乘用车-累计", indicator="批发"
    )
    print(car_market_man_rank_cpca_df)

    car_market_man_rank_cpca_df = car_market_man_rank_cpca(
        symbol="广义乘用车-单月", indicator="批发"
    )
    print(car_market_man_rank_cpca_df)

    car_market_man_rank_cpca_df = car_market_man_rank_cpca(
        symbol="广义乘用车-累计", indicator="批发"
    )
    print(car_market_man_rank_cpca_df)

    car_market_man_rank_cpca_df = car_market_man_rank_cpca(
        symbol="狭义乘用车-单月", indicator="零售"
    )
    print(car_market_man_rank_cpca_df)

    car_market_man_rank_cpca_df = car_market_man_rank_cpca(
        symbol="狭义乘用车-累计", indicator="零售"
    )
    print(car_market_man_rank_cpca_df)

    car_market_man_rank_cpca_df = car_market_man_rank_cpca(
        symbol="广义乘用车-单月", indicator="零售"
    )
    print(car_market_man_rank_cpca_df)

    car_market_man_rank_cpca_df = car_market_man_rank_cpca(
        symbol="广义乘用车-累计", indicator="零售"
    )
    print(car_market_man_rank_cpca_df)

    car_market_cate_cpca_df = car_market_cate_cpca(symbol="轿车", indicator="批发")
    print(car_market_cate_cpca_df)

    car_market_cate_cpca_df = car_market_cate_cpca(symbol="MPV", indicator="批发")
    print(car_market_cate_cpca_df)

    car_market_cate_cpca_df = car_market_cate_cpca(symbol="SUV", indicator="批发")
    print(car_market_cate_cpca_df)

    car_market_cate_cpca_df = car_market_cate_cpca(symbol="占比", indicator="批发")
    print(car_market_cate_cpca_df)

    car_market_cate_cpca_df = car_market_cate_cpca(symbol="轿车", indicator="零售")
    print(car_market_cate_cpca_df)

    car_market_cate_cpca_df = car_market_cate_cpca(symbol="MPV", indicator="零售")
    print(car_market_cate_cpca_df)

    car_market_cate_cpca_df = car_market_cate_cpca(symbol="SUV", indicator="零售")
    print(car_market_cate_cpca_df)

    car_market_cate_cpca_df = car_market_cate_cpca(symbol="占比", indicator="零售")
    print(car_market_cate_cpca_df)

    car_market_country_cpca_df = car_market_country_cpca()
    print(car_market_country_cpca_df)

    car_market_segment_cpca_df = car_market_segment_cpca(symbol="轿车")
    print(car_market_segment_cpca_df)

    car_market_segment_cpca_df = car_market_segment_cpca(symbol="MPV")
    print(car_market_segment_cpca_df)

    car_market_segment_cpca_df = car_market_segment_cpca(symbol="SUV")
    print(car_market_segment_cpca_df)

    car_market_fuel_cpca_df = car_market_fuel_cpca(symbol="整体市场")
    print(car_market_fuel_cpca_df)

    car_market_fuel_cpca_df = car_market_fuel_cpca(symbol="销量占比-PHEV-BEV")
    print(car_market_fuel_cpca_df)

    car_market_fuel_cpca_df = car_market_fuel_cpca(symbol="销量占比-ICE-NEV")
    print(car_market_fuel_cpca_df)
