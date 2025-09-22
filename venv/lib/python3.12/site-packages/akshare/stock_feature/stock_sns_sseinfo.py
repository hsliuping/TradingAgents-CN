#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/21 19:20
Desc: 上证e互动-提问与回答
https://sns.sseinfo.com/
"""

import warnings
from functools import lru_cache

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.utils.tqdm import get_tqdm


@lru_cache()
def _fetch_stock_uid() -> dict:
    """
    上证e互动-代码ID映射
    https://sns.sseinfo.com/list/company.do
    :return: 代码ID映射
    :rtype: str
    """
    url = "https://sns.sseinfo.com/allcompany.do"
    data = {
        "code": "0",
        "order": "2",
        "areaId": "0",
        "page": "1",
    }
    uid_list = list()
    code_list = list()
    tqdm = get_tqdm()
    for page in tqdm(range(1, 73), leave=False):
        data.update({"page": page})
        r = requests.post(url, data=data)
        data_json = r.json()
        soup = BeautifulSoup(data_json["content"], features="lxml")
        soup.find_all(name="a", attrs={"rel": "tag"})
        uid_list.extend(
            [item["uid"] for item in soup.find_all(name="a", attrs={"rel": "tag"})]
        )
        code_list.extend(
            [
                item.find("img")["src"].split("?")[0].split("/")[-1].split(".")[0]
                for item in soup.find_all(name="a", attrs={"rel": "tag"})
            ]
        )
    code_uid_map = dict(zip(code_list, uid_list))
    return code_uid_map


def stock_sns_sseinfo(symbol: str = "603119") -> pd.DataFrame:
    """
    上证e互动-提问与回答
    https://sns.sseinfo.com/company.do?uid=65
    :param symbol: 股票代码
    :type symbol: str
    :return: 提问与回答
    :rtype: str
    """
    code_uid_map = _fetch_stock_uid()
    url = "https://sns.sseinfo.com/ajax/userfeeds.do"
    params = {
        "typeCode": "company",
        "type": "11",
        "pageSize": "100",
        "uid": code_uid_map[symbol],
        "page": "1",
    }
    big_df = pd.DataFrame()
    page = 1
    warnings.warn("正在下载中")
    while True:
        params.update({"page": page})
        r = requests.post(url, params=params)
        if len(r.text) < 300:
            break
        else:
            page += 1
        r = requests.post(url, params=params)
        soup = BeautifulSoup(r.text, features="lxml")
        content_list = [
            item.get_text().strip()
            for item in soup.find_all(name="div", attrs={"class": "m_feed_txt"})
        ]
        date_list = [
            item.get_text().strip().split("\n")[0]
            for item in soup.find_all(name="div", attrs={"class": "m_feed_from"})
        ]
        source_list = [
            item.get_text().strip().split("\n")[2]
            for item in soup.find_all(name="div", attrs={"class": "m_feed_from"})
        ]
        q_list = [
            item.split(")")[1]
            for index, item in enumerate(content_list)
            if index % 2 == 0
        ]
        stock_name = [
            item.split("(")[0].strip(":")
            for index, item in enumerate(content_list)
            if index % 2 == 0
        ]
        stock_code = [
            item.split("(")[1].split(")")[0]
            for index, item in enumerate(content_list)
            if index % 2 == 0
        ]
        a_list = [item for index, item in enumerate(content_list) if index % 2 != 0]
        d_q_list = [item for index, item in enumerate(date_list) if index % 2 == 0]
        d_a_list = [item for index, item in enumerate(date_list) if index % 2 != 0]
        s_q_list = [item for index, item in enumerate(source_list) if index % 2 == 0]
        s_a_list = [item for index, item in enumerate(source_list) if index % 2 != 0]
        author_name = [
            item["title"] for item in soup.find_all(name="a", attrs={"rel": "face"})
        ]
        temp_df = pd.DataFrame(
            [
                stock_code,
                stock_name,
                q_list,
                a_list,
                d_q_list,
                d_a_list,
                s_q_list,
                s_a_list,
                author_name,
            ]
        ).T
        temp_df.columns = [
            "股票代码",
            "公司简称",
            "问题",
            "回答",
            "问题时间",
            "回答时间",
            "问题来源",
            "回答来源",
            "用户名",
        ]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    return big_df


if __name__ == "__main__":
    stock_sns_sseinfo_df = stock_sns_sseinfo(symbol="603119")
    print(stock_sns_sseinfo_df)
