#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/6/25 15:00
Desc: 碳排放交易
北京市碳排放权电子交易平台-北京市碳排放权公开交易行情
https://www.bjets.com.cn/article/jyxx/

深圳碳排放交易所-国内碳情
http://www.cerx.cn/dailynewsCN/index.htm

深圳碳排放交易所-国际碳情
http://www.cerx.cn/dailynewsOuter/index.htm

湖北碳排放权交易中心-现货交易数据-配额-每日概况
http://www.cerx.cn/dailynewsOuter/index.htm

广州碳排放权交易中心-行情信息
http://www.cnemission.com/article/hqxx/
"""

from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from akshare.utils import demjson
from akshare.utils.cons import headers


def energy_carbon_domestic(symbol: str = "湖北") -> pd.DataFrame:
    """
    碳交易网-行情信息
    http://www.tanjiaoyi.com/
    :param symbol: choice of {'湖北', '上海', '北京', '重庆', '广东', '天津', '深圳', '福建'}
    :type symbol: str
    :return: 行情信息
    :rtype: pandas.DataFrame
    """
    url = "http://k.tanjiaoyi.com:8080/KDataController/getHouseDatasInAverage.do"
    params = {
        "lcnK": "53f75bfcefff58e4046ccfa42171636c",
        "brand": "TAN",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("(") + 1 : -1])
    temp_df = pd.DataFrame(data_json[symbol])
    temp_df.columns = [
        "成交价",
        "_",
        "成交量",
        "地点",
        "成交额",
        "日期",
        "_",
    ]
    temp_df = temp_df[
        [
            "日期",
            "成交价",
            "成交量",
            "成交额",
            "地点",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["成交价"] = pd.to_numeric(temp_df["成交价"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    return temp_df


def energy_carbon_bj() -> pd.DataFrame:
    """
    北京市碳排放权电子交易平台-北京市碳排放权公开交易行情
    https://www.bjets.com.cn/article/jyxx/
    :return: 北京市碳排放权公开交易行情
    :rtype: pandas.DataFrame
    """
    url = "https://www.bjets.com.cn/article/jyxx/"
    r = requests.get(url, verify=False, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    total_page = (
        soup.find("table")
        .find("script")
        .string.split("=")[-1]
        .strip()
        .strip(";")
        .strip('"')
    )
    temp_df = pd.DataFrame()
    for i in tqdm(
        range(1, int(total_page) + 1),
        desc="Please wait for a moment",
        leave=False,
    ):
        if i == 1:
            i = ""
        url = f"https://www.bjets.com.cn/article/jyxx/?{i}"
        r = requests.get(url, verify=False, headers=headers)
        r.encoding = "utf-8"
        df = pd.read_html(StringIO(r.text))[0]
        temp_df = pd.concat(objs=[temp_df, df], ignore_index=True)
    temp_df.columns = ["日期", "成交量", "成交均价", "成交额"]
    temp_df["成交单位"] = (
        temp_df["成交额"]
        .str.split("(", expand=True)
        .iloc[:, 1]
        .str.split("）", expand=True)
        .iloc[:, 0]
        .str.split(")", expand=True)
        .iloc[:, 0]
    )
    temp_df["成交额"] = (
        temp_df["成交额"]
        .str.split("(", expand=True)
        .iloc[:, 0]
        .str.split("（", expand=True)
        .iloc[:, 0]
    )
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交均价"] = pd.to_numeric(temp_df["成交均价"], errors="coerce")
    temp_df["成交额"] = temp_df["成交额"].str.replace(",", "")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df.sort_values(by="日期", inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


def energy_carbon_sz() -> pd.DataFrame:
    """
    深圳碳排放交易所-国内碳情
    http://www.cerx.cn/dailynewsCN/index.htm
    :return: 国内碳情每日行情数据
    :rtype: pandas.DataFrame
    """
    url = "http://www.cerx.cn/dailynewsCN/index.htm"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    page_num = int(soup.find(attrs={"class": "pagebar"}).find_all("option")[-1].text)
    big_df = pd.read_html(StringIO(r.text), header=0)[0]
    for page in tqdm(
        range(2, page_num + 1), desc="Please wait for a moment", leave=False
    ):
        url = f"http://www.cerx.cn/dailynewsCN/index_{page}.htm"
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text), header=0)[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df["交易日期"] = pd.to_datetime(big_df["交易日期"], errors="coerce").dt.date
    big_df["开盘价"] = pd.to_numeric(big_df["开盘价"], errors="coerce")
    big_df["最高价"] = pd.to_numeric(big_df["最高价"], errors="coerce")
    big_df["最低价"] = pd.to_numeric(big_df["最低价"], errors="coerce")
    big_df["成交均价"] = pd.to_numeric(big_df["成交均价"], errors="coerce")
    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["成交额"] = pd.to_numeric(big_df["成交额"], errors="coerce")
    big_df.sort_values(by="交易日期", inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def energy_carbon_eu() -> pd.DataFrame:
    """
    深圳碳排放交易所-国际碳情
    http://www.cerx.cn/dailynewsOuter/index.htm
    :return: 国际碳情每日行情数据
    :rtype: pandas.DataFrame
    """
    url = "http://www.cerx.cn/dailynewsOuter/index.htm"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    page_num = int(soup.find(attrs={"class": "pagebar"}).find_all("option")[-1].text)
    big_df = pd.read_html(StringIO(r.text), header=0)[0]
    for page in tqdm(
        range(2, page_num + 1), desc="Please wait for a moment", leave=False
    ):
        url = f"http://www.cerx.cn/dailynewsOuter/index_{page}.htm"
        r = requests.get(url)
        temp_df = pd.read_html(StringIO(r.text), header=0)[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df["交易日期"] = pd.to_datetime(big_df["交易日期"], errors="coerce").dt.date
    big_df["开盘价"] = pd.to_numeric(big_df["开盘价"], errors="coerce")
    big_df["最高价"] = pd.to_numeric(big_df["最高价"], errors="coerce")
    big_df["最低价"] = pd.to_numeric(big_df["最低价"], errors="coerce")
    big_df["成交均价"] = pd.to_numeric(big_df["成交均价"], errors="coerce")
    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["成交额"] = pd.to_numeric(big_df["成交额"], errors="coerce")
    big_df.sort_values(by="交易日期", inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def energy_carbon_hb() -> pd.DataFrame:
    """
    湖北碳排放权交易中心-现货交易数据-配额-每日概况
    http://www.hbets.cn/list/13.html?page=42
    :return: 现货交易数据-配额-每日概况行情数据
    :rtype: pandas.DataFrame
    """
    url = "https://www.hbets.cn/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    data_text = (
        soup.find(name="div", attrs={"class": "threeLeft"}).find_all("script")[1].text
    )
    start_pos = data_text.find("cjj = '[") + 7  # 找到 JSON 数组开始的位置
    end_pos = data_text.rfind("cjj =") - 31  # 找到 JSON 数组结束的位置
    data_json = demjson.decode(data_text[start_pos:end_pos])
    temp_df = pd.DataFrame.from_dict(data_json)
    temp_df.rename(
        columns={
            "riqi": "日期",
            "cjj": "成交价",
            "cjl": "成交量",
            "zx": "最新",
            "zd": "涨跌",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "日期",
            "成交价",
            "成交量",
            "最新",
            "涨跌",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["成交价"] = pd.to_numeric(temp_df["成交价"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["最新"] = pd.to_numeric(temp_df["最新"], errors="coerce")
    temp_df["涨跌"] = pd.to_numeric(temp_df["涨跌"], errors="coerce")
    return temp_df


def energy_carbon_gz() -> pd.DataFrame:
    """
    广州碳排放权交易中心-行情信息
    http://www.cnemission.com/article/hqxx/
    :return: 行情信息数据
    :rtype: pandas.DataFrame
    """
    url = "http://ets.cnemission.com/carbon/portalIndex/markethistory"
    params = {
        "Top": "1",
        "beginTime": "2010-01-01",
        "endTime": "2030-09-12",
    }
    r = requests.get(url, params=params)
    temp_df = pd.read_html(StringIO(r.text), header=0)[1]
    temp_df.columns = [
        "日期",
        "品种",
        "开盘价",
        "收盘价",
        "最高价",
        "最低价",
        "涨跌",
        "涨跌幅",
        "成交数量",
        "成交金额",
    ]
    temp_df["日期"] = pd.to_datetime(
        temp_df["日期"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df["开盘价"] = pd.to_numeric(temp_df["开盘价"], errors="coerce")
    temp_df["收盘价"] = pd.to_numeric(temp_df["收盘价"], errors="coerce")
    temp_df["最高价"] = pd.to_numeric(temp_df["最高价"], errors="coerce")
    temp_df["最低价"] = pd.to_numeric(temp_df["最低价"], errors="coerce")
    temp_df["涨跌"] = pd.to_numeric(temp_df["涨跌"], errors="coerce")
    temp_df["涨跌幅"] = temp_df["涨跌幅"].str.strip("%")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["成交数量"] = pd.to_numeric(temp_df["成交数量"], errors="coerce")
    temp_df["成交金额"] = pd.to_numeric(temp_df["成交金额"], errors="coerce")
    temp_df.sort_values(by="日期", inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


if __name__ == "__main__":
    energy_carbon_domestic_df = energy_carbon_domestic(symbol="湖北")
    print(energy_carbon_domestic_df)

    energy_carbon_domestic_df = energy_carbon_domestic(symbol="深圳")
    print(energy_carbon_domestic_df)

    energy_carbon_bj_df = energy_carbon_bj()
    print(energy_carbon_bj_df)

    energy_carbon_sz_df = energy_carbon_sz()
    print(energy_carbon_sz_df)

    energy_carbon_eu_df = energy_carbon_eu()
    print(energy_carbon_eu_df)

    energy_carbon_hb_df = energy_carbon_hb()
    print(energy_carbon_hb_df)

    energy_carbon_gz_df = energy_carbon_gz()
    print(energy_carbon_gz_df)
