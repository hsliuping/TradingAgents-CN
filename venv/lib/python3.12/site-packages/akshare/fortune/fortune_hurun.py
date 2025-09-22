#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/12/22 20:00
Desc: 胡润排行榜
https://www.hurun.net/
"""

import warnings

import pandas as pd
import requests
from bs4 import BeautifulSoup


def hurun_rank(indicator: str = "胡润百富榜", year: str = "2023") -> pd.DataFrame:
    """
    胡润排行榜
    https://www.hurun.net/CN/HuList/Index?num=3YwKs889SRIm
    :param indicator: choice of {"胡润百富榜", "胡润全球富豪榜", "胡润印度榜", "胡润全球独角兽榜", "全球瞪羚企业榜", "胡润Under30s创业领袖榜", "胡润中国500强民营企业", "胡润世界500强", "胡润艺术榜"}
    :type indicator: str
    :param year: 指定年份; {"胡润百富榜": "2014-至今", "胡润全球富豪榜": "2019-至今", "胡润印度榜": "2018-至今", "胡润全球独角兽榜": "2019-至今", "中国瞪羚企业榜": "2021-至今", "全球瞪羚企业榜": "2021-至今", "胡润Under30s创业领袖榜": "2019-至今", "胡润中国500强民营企业": "2019-至今", "胡润世界500强": "2020-至今", "胡润艺术榜": "2019-至今"}
    :type year: str
    :return: 指定 indicator 和 year 的数据
    :rtype: pandas.DataFrame
    """
    url = "https://www.hurun.net/zh-CN/Rank/HsRankDetails?pagetype=rich"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    url_list = []
    for item in soup.find_all("ul", attrs={"class": "dropdown-menu"}):
        for inner_item in item.find_all("a"):
            url_list.append("https://www.hurun.net" + inner_item["href"])
    name_list = []
    for item in soup.find_all("ul", attrs={"class": "dropdown-menu"}):
        for inner_item in item.find_all("a"):
            name_list.append(inner_item.text.strip())

    name_url_map = dict(zip(name_list, url_list))
    r = requests.get(name_url_map[indicator])
    soup = BeautifulSoup(r.text, "lxml")
    code_list = [
        item["value"].split("=")[2]
        for item in soup.find(attrs={"id": "exampleFormControlSelect1"}).find_all(
            "option"
        )
    ]
    year_list = [
        item.text.split(" ")[0]
        for item in soup.find(attrs={"id": "exampleFormControlSelect1"}).find_all(
            "option"
        )
    ]
    year_code_map = dict(zip(year_list, code_list))
    params = {
        "num": year_code_map[year],
        "search": "",
        "offset": "0",
        "limit": "20000",
    }
    if year == "2018":
        warnings.warn("正在下载中")
        offset = 0
        limit = 20
        big_df = pd.DataFrame()
        while offset < 2200:
            try:
                params.update(
                    {
                        "offset": offset,
                        "limit": limit,
                    }
                )
                url = "https://www.hurun.net/zh-CN/Rank/HsRankDetailsList"
                r = requests.get(url, params=params)
                data_json = r.json()
                temp_df = pd.DataFrame(data_json["rows"])
                offset = offset + 20
                big_df = pd.concat([big_df, temp_df], ignore_index=True)
            except requests.exceptions.JSONDecodeError:
                offset = offset + 40
                continue
        big_df.rename(
            columns={
                "hs_Rank_Rich_Ranking": "排名",
                "hs_Rank_Rich_Wealth": "财富",
                "hs_Rank_Rich_Ranking_Change": "排名变化",
                "hs_Rank_Rich_ChaName_Cn": "姓名",
                "hs_Rank_Rich_ComName_Cn": "企业",
                "hs_Rank_Rich_Industry_Cn": "行业",
            },
            inplace=True,
        )
        big_df = big_df[
            [
                "排名",
                "财富",
                "姓名",
                "企业",
                "行业",
            ]
        ]
        return big_df
    url = "https://www.hurun.net/zh-CN/Rank/HsRankDetailsList"
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["rows"])
    if indicator == "胡润百富榜":
        temp_df.rename(
            columns={
                "hs_Rank_Rich_Ranking": "排名",
                "hs_Rank_Rich_Wealth": "财富",
                "hs_Rank_Rich_Ranking_Change": "排名变化",
                "hs_Rank_Rich_ChaName_Cn": "姓名",
                "hs_Rank_Rich_ComName_Cn": "企业",
                "hs_Rank_Rich_Industry_Cn": "行业",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "排名",
                "财富",
                "姓名",
                "企业",
                "行业",
            ]
        ]
    elif indicator == "胡润全球富豪榜":
        temp_df.rename(
            columns={
                "hs_Rank_Global_Ranking": "排名",
                "hs_Rank_Global_Wealth": "财富",
                "hs_Rank_Global_Ranking_Change": "排名变化",
                "hs_Rank_Global_ChaName_Cn": "姓名",
                "hs_Rank_Global_ComName_Cn": "企业",
                "hs_Rank_Global_Industry_Cn": "行业",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "排名",
                "财富",
                "姓名",
                "企业",
                "行业",
            ]
        ]
    elif indicator == "胡润印度榜":
        temp_df.rename(
            columns={
                "hs_Rank_India_Ranking": "排名",
                "hs_Rank_India_Wealth": "财富",
                "hs_Rank_India_Ranking_Change": "排名变化",
                "hs_Rank_India_ChaName_Cn": "姓名",
                "hs_Rank_India_ComName_Cn": "企业",
                "hs_Rank_India_Industry_Cn": "行业",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "排名",
                "财富",
                "姓名",
                "企业",
                "行业",
            ]
        ]
    elif indicator == "胡润全球独角兽榜":
        temp_df.rename(
            columns={
                "hs_Rank_Unicorn_Ranking": "排名",
                "hs_Rank_Unicorn_Wealth": "财富",
                "hs_Rank_Unicorn_Ranking_Change": "排名变化",
                "hs_Rank_Unicorn_ChaName_Cn": "姓名",
                "hs_Rank_Unicorn_ComName_Cn": "企业",
                "hs_Rank_Unicorn_Industry_Cn": "行业",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "排名",
                "财富",
                "姓名",
                "企业",
                "行业",
            ]
        ]
    elif indicator == "中国瞪羚企业榜":
        temp_df.rename(
            columns={
                "hs_Rank_CGazelles_ComHeadquarters_Cn": "企业总部",
                "hs_Rank_CGazelles_Name_Cn": "掌门人/联合创始人",
                "hs_Rank_CGazelles_ComName_Cn": "企业信息",
                "hs_Rank_CGazelles_Industry_Cn": "行业",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "企业信息",
                "掌门人/联合创始人",
                "企业总部",
                "行业",
            ]
        ]
    elif indicator == "全球瞪羚企业榜":
        temp_df.rename(
            columns={
                "hs_Rank_GGazelles_ComHeadquarters_Cn": "企业总部",
                "hs_Rank_GGazelles_Name_Cn": "掌门人/联合创始人",
                "hs_Rank_GGazelles_ComName_Cn": "企业信息",
                "hs_Rank_GGazelles_Industry_Cn": "行业",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "企业信息",
                "掌门人/联合创始人",
                "企业总部",
                "行业",
            ]
        ]
    elif indicator == "胡润Under30s创业领袖榜":
        temp_df.rename(
            columns={
                "hs_Rank_U30_ComHeadquarters_Cn": "企业总部",
                "hs_Rank_U30_ChaName_Cn": "姓名",
                "hs_Rank_U30_ComName_Cn": "企业信息",
                "hs_Rank_U30_Industry_Cn": "行业",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "姓名",
                "企业信息",
                "企业总部",
                "行业",
            ]
        ]
    elif indicator == "胡润中国500强民营企业":
        temp_df.rename(
            columns={
                "hs_Rank_CTop500_Ranking": "排名",
                "hs_Rank_CTop500_Wealth": "企业估值",
                "hs_Rank_CTop500_Ranking_Change": "排名变化",
                "hs_Rank_CTop500_ChaName_Cn": "CEO",
                "hs_Rank_CTop500_ComName_Cn": "企业信息",
                "hs_Rank_CTop500_Industry_Cn": "行业",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "排名",
                "排名变化",
                "企业估值",
                "企业信息",
                "CEO",
                "行业",
            ]
        ]
    elif indicator == "胡润世界500强":
        temp_df.rename(
            columns={
                "hs_Rank_GTop500_Ranking": "排名",
                "hs_Rank_GTop500_Wealth": "企业估值",
                "hs_Rank_GTop500_Ranking_Change": "排名变化",
                "hs_Rank_GTop500_ChaName_Cn": "CEO",
                "hs_Rank_GTop500_ComName_Cn": "企业信息",
                "hs_Rank_GTop500_Industry_Cn": "行业",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "排名",
                "排名变化",
                "企业估值",
                "企业信息",
                "CEO",
                "行业",
            ]
        ]
    elif indicator == "胡润艺术榜":
        temp_df.rename(
            columns={
                "hs_Rank_Art_Ranking": "排名",
                "hs_Rank_Art_Turnover": "成交额",
                "hs_Rank_Art_Ranking_Change": "排名变化",
                "hs_Rank_Art_Name_Cn": "姓名",
                "hs_Rank_Art_Age": "年龄",
                "hs_Rank_Art_ArtCategory_Cn": "艺术类别",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "排名",
                "排名变化",
                "成交额",
                "姓名",
                "年龄",
                "艺术类别",
            ]
        ]
    return temp_df


if __name__ == "__main__":
    hurun_rank_df = hurun_rank(indicator="胡润百富榜", year="2023")
    print(hurun_rank_df)

    hurun_rank_df = hurun_rank(indicator="胡润全球富豪榜", year="2023")
    print(hurun_rank_df)

    hurun_rank_df = hurun_rank(indicator="胡润全球独角兽榜", year="2023")
    print(hurun_rank_df)

    hurun_rank_df = hurun_rank(indicator="胡润印度榜", year="2021")
    print(hurun_rank_df)

    hurun_rank_df = hurun_rank(indicator="全球瞪羚企业榜", year="2021")
    print(hurun_rank_df)

    hurun_rank_df = hurun_rank(indicator="胡润Under30s创业领袖榜", year="2021")
    print(hurun_rank_df)

    hurun_rank_df = hurun_rank(indicator="胡润世界500强", year="2022")
    print(hurun_rank_df)

    hurun_rank_df = hurun_rank(indicator="胡润艺术榜", year="2023")
    print(hurun_rank_df)
