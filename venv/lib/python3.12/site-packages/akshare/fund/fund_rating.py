#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/12/12 16:30
Desc: 基金评级
https://fund.eastmoney.com/data/fundrating.html
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup


def fund_rating_all() -> pd.DataFrame:
    """
    天天基金网-基金评级-基金评级总汇
    https://fund.eastmoney.com/data/fundrating.html
    :return: 基金评级总汇
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/data/fundrating.html"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    data_text = soup.find("div", attrs={"id": "fundinfo"}).find("script").string
    data_content = [
        item.split("|")
        for item in data_text.split("var")[6]
        .split("=")[1]
        .strip()
        .strip(";")
        .strip('"')
        .strip("|")
        .split("|_")
    ]
    temp_df = pd.DataFrame(data_content)
    temp_df.columns = [
        "代码",
        "简称",
        "类型",
        "基金经理",
        "-",
        "基金公司",
        "-",
        "5星评级家数",
        "-",
        "-",
        "招商证券",
        "-",
        "上海证券",
        "-",
        "-",
        "-",
        "济安金信",
        "-",
        "手续费",
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
            "简称",
            "基金经理",
            "基金公司",
            "5星评级家数",
            "上海证券",
            "招商证券",
            "济安金信",
            "手续费",
            "类型",
        ]
    ]
    temp_df["5星评级家数"] = pd.to_numeric(temp_df["5星评级家数"], errors="coerce")
    temp_df["上海证券"] = pd.to_numeric(temp_df["上海证券"], errors="coerce")
    temp_df["招商证券"] = pd.to_numeric(temp_df["招商证券"], errors="coerce")
    temp_df["济安金信"] = pd.to_numeric(temp_df["济安金信"], errors="coerce")
    temp_df["手续费"] = (
        pd.to_numeric(temp_df["手续费"].str.strip("%"), errors="coerce") / 100
    )
    return temp_df


def fund_rating_sh(date: str = "20230630") -> pd.DataFrame:
    """
    天天基金网-基金评级-上海证券评级
    https://fund.eastmoney.com/data/fundrating_3.html
    :param date: 日期; https://fund.eastmoney.com/data/fundrating_3.html 获取查询日期
    :type date: str
    :return: 上海证券评级
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/data/fundrating_3.html"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    date_list = [
        item["value"] for item in soup.find("select", attrs={"id": "rqoptions"})
    ]
    date_format = "-".join([date[:4], date[4:6], date[6:]])
    if date_format not in date_list:
        raise "请访问 https://fund.eastmoney.com/data/fundrating_3.html 获取查询日期"
    url = f"https://fund.eastmoney.com/data/fundrating_3_{'-'.join([date[:4], date[4:6], date[6:]])}.html"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    data_text = soup.find("div", attrs={"id": "fundinfo"}).find("script").string
    data_content = [
        item.split("|")
        for item in data_text.split("var")[1]
        .split("=")[1]
        .strip()
        .strip(";")
        .strip('"')
        .strip("|")
        .split("|_")
    ]
    temp_df = pd.DataFrame(data_content)
    temp_df.columns = [
        "代码",
        "简称",
        "类型",
        "基金经理",
        "_",
        "基金公司",
        "_",
        "3年期评级-3年评级",
        "3年期评级-较上期",
        "5年期评级-5年评级",
        "5年期评级-较上期",
        "单位净值",
        "日期",
        "日增长率",
        "近1年涨幅",
        "近3年涨幅",
        "近5年涨幅",
        "手续费",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "代码",
            "简称",
            "基金经理",
            "基金公司",
            "3年期评级-3年评级",
            "3年期评级-较上期",
            "5年期评级-5年评级",
            "5年期评级-较上期",
            "单位净值",
            "日期",
            "日增长率",
            "近1年涨幅",
            "近3年涨幅",
            "近5年涨幅",
            "手续费",
            "类型",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["3年期评级-3年评级"] = pd.to_numeric(
        temp_df["3年期评级-3年评级"], errors="coerce"
    )
    temp_df["3年期评级-较上期"] = pd.to_numeric(
        temp_df["3年期评级-较上期"], errors="coerce"
    )
    temp_df["5年期评级-5年评级"] = pd.to_numeric(
        temp_df["5年期评级-5年评级"], errors="coerce"
    )
    temp_df["5年期评级-较上期"] = pd.to_numeric(
        temp_df["5年期评级-较上期"], errors="coerce"
    )
    temp_df["单位净值"] = pd.to_numeric(temp_df["单位净值"], errors="coerce")
    temp_df["日增长率"] = pd.to_numeric(temp_df["日增长率"], errors="coerce")
    temp_df["近1年涨幅"] = pd.to_numeric(temp_df["近1年涨幅"], errors="coerce")
    temp_df["近3年涨幅"] = pd.to_numeric(temp_df["近3年涨幅"], errors="coerce")
    temp_df["近5年涨幅"] = pd.to_numeric(temp_df["近5年涨幅"], errors="coerce")
    return temp_df


def fund_rating_zs(date: str = "20230331") -> pd.DataFrame:
    """
    天天基金网-基金评级-招商证券评级
    https://fund.eastmoney.com/data/fundrating_2.html
    :param date: 日期; https://fund.eastmoney.com/data/fundrating_2.html 获取查询日期
    :type date: str
    :return: 招商证券评级-混合型
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/data/fundrating_2.html"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    date_list = [
        item["value"] for item in soup.find("select", attrs={"id": "rqoptions"})
    ]
    date_format = "-".join([date[:4], date[4:6], date[6:]])
    if date_format not in date_list:
        raise "请访问 https://fund.eastmoney.com/data/fundrating_2.html 获取查询日期"
    url = f"https://fund.eastmoney.com/data/fundrating_2_{'-'.join([date[:4], date[4:6], date[6:]])}.html"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    data_text = soup.find("div", attrs={"id": "fundinfo"}).find("script").string
    data_content = [
        item.split("|")
        for item in data_text.split("var")[1]
        .split("=")[1]
        .strip()
        .strip(";")
        .strip('"')
        .strip("|")
        .split("|_")
    ]
    temp_df = pd.DataFrame(data_content)
    temp_df.columns = [
        "代码",
        "简称",
        "_",
        "基金经理",
        "_",
        "基金公司",
        "_",
        "3年期评级-3年评级",
        "3年期评级-较上期",
        "单位净值",
        "日期",
        "日增长率",
        "近1年涨幅",
        "近3年涨幅",
        "近5年涨幅",
        "手续费",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "代码",
            "简称",
            "基金经理",
            "基金公司",
            "3年期评级-3年评级",
            "3年期评级-较上期",
            "单位净值",
            "日期",
            "日增长率",
            "近1年涨幅",
            "近3年涨幅",
            "近5年涨幅",
            "手续费",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["3年期评级-3年评级"] = pd.to_numeric(
        temp_df["3年期评级-3年评级"], errors="coerce"
    )
    temp_df["3年期评级-较上期"] = pd.to_numeric(
        temp_df["3年期评级-较上期"], errors="coerce"
    )
    temp_df["单位净值"] = pd.to_numeric(temp_df["单位净值"], errors="coerce")
    temp_df["日增长率"] = pd.to_numeric(temp_df["日增长率"], errors="coerce")
    temp_df["近1年涨幅"] = pd.to_numeric(temp_df["近1年涨幅"], errors="coerce")
    temp_df["近3年涨幅"] = pd.to_numeric(temp_df["近3年涨幅"], errors="coerce")
    temp_df["近5年涨幅"] = pd.to_numeric(temp_df["近5年涨幅"], errors="coerce")
    return temp_df


def fund_rating_ja(date: str = "20230331") -> pd.DataFrame:
    """
    天天基金网-基金评级-济安金信评级
    https://fund.eastmoney.com/data/fundrating_4.html
    :param date: 日期; https://fund.eastmoney.com/data/fundrating_4.html 获取查询日期
    :type date: str
    :return: 济安金信评级
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/data/fundrating_4.html"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    date_list = [
        item["value"] for item in soup.find("select", attrs={"id": "rqoptions"})
    ]
    date_format = "-".join([date[:4], date[4:6], date[6:]])
    if date_format not in date_list:
        raise "请访问 http://fund.eastmoney.com/data/fundrating_4.html 获取查询日期"
    url = f"https://fund.eastmoney.com/data/fundrating_4_{'-'.join([date[:4], date[4:6], date[6:]])}.html"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    data_text = soup.find("div", attrs={"id": "fundinfo"}).find("script").string
    data_content = [
        item.split("|")
        for item in data_text.split("var")[1]
        .split("=")[1]
        .strip()
        .strip(";")
        .strip('"')
        .strip("|")
        .split("|_")
    ]
    temp_df = pd.DataFrame(data_content)
    temp_df.columns = [
        "代码",
        "简称",
        "类型",
        "基金经理",
        "_",
        "基金公司",
        "_",
        "3年期评级-3年评级",
        "3年期评级-较上期",
        "单位净值",
        "日期",
        "日增长率",
        "近1年涨幅",
        "近3年涨幅",
        "近5年涨幅",
        "手续费",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "代码",
            "简称",
            "基金经理",
            "基金公司",
            "3年期评级-3年评级",
            "3年期评级-较上期",
            "单位净值",
            "日期",
            "日增长率",
            "近1年涨幅",
            "近3年涨幅",
            "近5年涨幅",
            "手续费",
            "类型",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["3年期评级-3年评级"] = pd.to_numeric(
        temp_df["3年期评级-3年评级"], errors="coerce"
    )
    temp_df["3年期评级-较上期"] = pd.to_numeric(
        temp_df["3年期评级-较上期"], errors="coerce"
    )
    temp_df["单位净值"] = pd.to_numeric(temp_df["单位净值"], errors="coerce")
    temp_df["日增长率"] = pd.to_numeric(temp_df["日增长率"], errors="coerce")
    temp_df["近1年涨幅"] = pd.to_numeric(temp_df["近1年涨幅"], errors="coerce")
    temp_df["近3年涨幅"] = pd.to_numeric(temp_df["近3年涨幅"], errors="coerce")
    temp_df["近5年涨幅"] = pd.to_numeric(temp_df["近5年涨幅"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    fund_rating_all_df = fund_rating_all()
    print(fund_rating_all_df)

    fund_rating_sh_df = fund_rating_sh(date="20230630")
    print(fund_rating_sh_df)

    fund_rating_zs_df = fund_rating_zs(date="20230331")
    print(fund_rating_zs_df)

    fund_rating_ja_df = fund_rating_ja(date="20230331")
    print(fund_rating_ja_df)
