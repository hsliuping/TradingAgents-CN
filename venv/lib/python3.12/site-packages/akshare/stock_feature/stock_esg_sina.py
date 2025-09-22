#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/7/15 16:30
Desc: 新浪财经-ESG评级中心
https://finance.sina.com.cn/esg/
"""

import math
from akshare.utils.tqdm import get_tqdm

import pandas as pd
import requests


def stock_esg_msci_sina() -> pd.DataFrame:
    """
    新浪财经-ESG评级中心-ESG评级-MSCI
    https://finance.sina.com.cn/esg/grade.shtml
    :return: MSCI
    :rtype: pandas.DataFrame
    """
    url = "https://global.finance.sina.com.cn/api/openapi.php/EsgService.getMsciEsgStocks?p=1&num=100"
    r = requests.get(url)
    data_json = r.json()
    page_num = math.ceil(int(data_json["result"]["data"]["total"]) / 100)
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        headers = {
            "Referer": "https://finance.sina.com.cn/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36",
        }
        url = f"https://global.finance.sina.com.cn/api/openapi.php/EsgService.getMsciEsgStocks?p={page}&num=100"
        r = requests.get(url, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.rename(
        columns={
            "agency_id": "-",
            "agency_name": "评级机构",
            "symbol": "股票代码",
            "delist": "-",
            "comp_code": "-",
            "name": "股票名称",
            "market": "交易市场",
            "industry_code": "行业代码",
            "industry_name": "行业名称",
            "sw1_code": "-",
            "sw1_name": "-",
            "sw2_code": "-",
            "sw2_name": "-",
            "sw3_code": "-",
            "sw3_name": "-",
            "hs1_code": "-",
            "hs1_name": "-",
            "hs2_code": "-",
            "hs2_name": "-",
            "hs3_code": "-",
            "hs3_name": "-",
            "factset_sector_code": "-",
            "factset_sector_name": "-",
            "factset_industry_code": "-",
            "factset_industry_name": "-",
            "date": "-",
            "quarter_date": "评级日期",
            "grade": "ESG等级",
            "score": "-",
            "env_score": "环境总评",
            "env_grade": "-",
            "social_score": "社会责任总评",
            "social_grade": "-",
            "governance_score": "治理总评",
            "governance_grade": "-",
            "change_status": "-",
            "updated_time": "更新时间",
            "created_time": "创建时间",
            "esg_rating": "ESG评分",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "股票代码",
            "ESG评分",
            "环境总评",
            "社会责任总评",
            "治理总评",
            "评级日期",
            "交易市场",
        ]
    ]
    big_df["评级日期"] = pd.to_datetime(big_df["评级日期"], errors="coerce").dt.date
    big_df["环境总评"] = pd.to_numeric(big_df["环境总评"], errors="coerce")
    big_df["社会责任总评"] = pd.to_numeric(big_df["社会责任总评"], errors="coerce")
    big_df["治理总评"] = pd.to_numeric(big_df["治理总评"], errors="coerce")
    return big_df


def stock_esg_rft_sina() -> pd.DataFrame:
    """
    新浪财经-ESG评级中心-ESG评级-路孚特
    https://finance.sina.com.cn/esg/grade.shtml
    :return: 路孚特
    :rtype: pandas.DataFrame
    """
    url = "https://global.finance.sina.com.cn/api/openapi.php/EsgService.getRftEsgStocks?p=1&num=20000"
    r = requests.get(url)
    data_json = r.json()
    big_df = pd.DataFrame(data_json["result"]["data"]["data"])
    big_df.rename(
        columns={
            "symbol": "股票代码",
            "esg_score": "ESG评分",
            "esg_score_date": "ESG评分日期",
            "env_score": "环境总评",
            "env_score_date": "环境总评日期",
            "social_score": "社会责任总评",
            "social_score_date": "社会责任总评日期",
            "governance_score": "治理总评",
            "governance_score_date": "治理总评日期",
            "zy_score": "争议总评",
            "zy_score_date": "争议总评日期",
            "industry": "行业",
            "exchange": "交易所",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "股票代码",
            "ESG评分",
            "ESG评分日期",
            "环境总评",
            "环境总评日期",
            "社会责任总评",
            "社会责任总评日期",
            "治理总评",
            "治理总评日期",
            "争议总评",
            "争议总评日期",
            "行业",
            "交易所",
        ]
    ]
    big_df["ESG评分日期"] = pd.to_datetime(
        big_df["ESG评分日期"], errors="coerce"
    ).dt.date
    big_df["环境总评日期"] = pd.to_datetime(
        big_df["环境总评日期"], errors="coerce"
    ).dt.date
    big_df["社会责任总评日期"] = pd.to_datetime(
        big_df["社会责任总评日期"], errors="coerce"
    ).dt.date
    big_df["治理总评日期"] = pd.to_datetime(
        big_df["治理总评日期"], errors="coerce"
    ).dt.date
    big_df["争议总评日期"] = pd.to_datetime(
        big_df["争议总评日期"], errors="coerce"
    ).dt.date
    return big_df


def stock_esg_rate_sina() -> pd.DataFrame:
    """
    新浪财经-ESG评级中心-ESG评级-ESG评级数据
    https://finance.sina.com.cn/esg/grade.shtml
    :return: ESG评级数据
    :rtype: pandas.DataFrame
    """
    url = "https://global.finance.sina.com.cn/api/openapi.php/EsgService.getEsgStocks?page=1&num=200"
    r = requests.get(url)
    data_json = r.json()
    page_num = math.ceil(int(data_json["result"]["data"]["info"]["total"]) / 200)
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        url = f"https://global.finance.sina.com.cn/api/openapi.php/EsgService.getEsgStocks?page={page}&num=200"
        r = requests.get(url)
        data_json = r.json()
        stock_num = len(data_json["result"]["data"]["info"]["stocks"])
        for num in range(stock_num):
            temp_df = pd.DataFrame(
                data_json["result"]["data"]["info"]["stocks"][num]["esg_info"]
            )
            temp_df["symbol"] = data_json["result"]["data"]["info"]["stocks"][num][
                "symbol"
            ]
            temp_df["market"] = data_json["result"]["data"]["info"]["stocks"][num][
                "market"
            ]
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.rename(
        columns={
            "symbol": "成分股代码",
            "agency_name": "评级机构",
            "esg_score": "评级",
            "esg_dt": "评级季度",
            "remark": "标识",
            "market": "交易市场",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "成分股代码",
            "评级机构",
            "评级",
            "评级季度",
            "标识",
            "交易市场",
        ]
    ]
    return big_df


def stock_esg_zd_sina() -> pd.DataFrame:
    """
    新浪财经-ESG评级中心-ESG评级-秩鼎
    https://finance.sina.com.cn/esg/grade.shtml
    :return: 秩鼎
    :rtype: pandas.DataFrame
    """
    url = "https://global.finance.sina.com.cn/api/openapi.php/EsgService.getZdEsgStocks"
    params = {"p": "1", "num": "100"}
    r = requests.get(url, params=params)
    data_json = r.json()
    tqdm = get_tqdm()
    total_page = math.ceil(int(data_json["result"]["data"]["total"]) / 100)
    temp_list = []
    for page in tqdm(range(1, total_page + 1), leave=False):
        params = {"p": str(page), "num": "100"}
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"]["data"])
        temp_list.append(temp_df)
    big_df = pd.concat(temp_list, ignore_index=True)
    big_df.rename(
        columns={
            "ticker": "股票代码",
            "esg_score": "ESG评分",
            "report_date": "评分日期",
            "environmental_score": "环境总评",
            "social_score": "社会责任总评",
            "governance_score": "治理总评",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "股票代码",
            "ESG评分",
            "环境总评",
            "社会责任总评",
            "治理总评",
            "评分日期",
        ]
    ]
    big_df["评分日期"] = pd.to_datetime(big_df["评分日期"], errors="coerce").dt.date
    return big_df


def stock_esg_hz_sina() -> pd.DataFrame:
    """
    新浪财经-ESG评级中心-ESG评级-华证指数
    https://finance.sina.com.cn/esg/grade.shtml
    :return: 华证指数
    :rtype: pandas.DataFrame
    """
    url = "https://global.finance.sina.com.cn/api/openapi.php/EsgService.getHzEsgStocks"
    params = {"p": 1, "num": "100"}
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = math.ceil(int(data_json["result"]["data"]["total"]) / 100)
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params = {"p": str(page), "num": "100"}
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.rename(
        columns={
            "date": "日期",
            "symbol": "股票代码",
            "market": "交易市场",
            "name": "股票名称",
            "esg_score": "ESG评分",
            "esg_score_grade": "ESG等级",
            "e_score": "环境",
            "e_score_grade": "环境等级",
            "s_score": "社会",
            "s_score_grade": "社会等级",
            "g_score": "公司治理",
            "g_score_grade": "公司治理等级",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "日期",
            "股票代码",
            "交易市场",
            "股票名称",
            "ESG评分",
            "ESG等级",
            "环境",
            "环境等级",
            "社会",
            "社会等级",
            "公司治理",
            "公司治理等级",
        ]
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["ESG评分"] = pd.to_numeric(big_df["ESG评分"], errors="coerce")
    big_df["环境"] = pd.to_numeric(big_df["环境"], errors="coerce")
    big_df["社会"] = pd.to_numeric(big_df["社会"], errors="coerce")
    big_df["公司治理"] = pd.to_numeric(big_df["公司治理"], errors="coerce")
    return big_df


if __name__ == "__main__":
    stock_esg_msci_sina_df = stock_esg_msci_sina()
    print(stock_esg_msci_sina_df)

    stock_esg_rft_sina_df = stock_esg_rft_sina()
    print(stock_esg_rft_sina_df)

    stock_esg_rate_sina_df = stock_esg_rate_sina()
    print(stock_esg_rate_sina_df)

    stock_esg_zd_sina_df = stock_esg_zd_sina()
    print(stock_esg_zd_sina_df)

    stock_esg_hz_sina_df = stock_esg_hz_sina()
    print(stock_esg_hz_sina_df)
