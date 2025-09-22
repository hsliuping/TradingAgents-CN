#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/8/15 18:00
Desc: 同花顺-数据中心-资金流向
同花顺-数据中心-资金流向-个股资金流
https://data.10jqka.com.cn/funds/ggzjl/#refCountId=data_55f13c2c_254
同花顺-数据中心-资金流向-概念资金流
https://data.10jqka.com.cn/funds/gnzjl/#refCountId=data_55f13c2c_254
同花顺-数据中心-资金流向-行业资金流
https://data.10jqka.com.cn/funds/hyzjl/#refCountId=data_55f13c2c_254
同花顺-数据中心-资金流向-打单追踪
https://data.10jqka.com.cn/funds/ddzz/#refCountId=data_55f13c2c_254
"""

from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup
import py_mini_racer
from akshare.utils.tqdm import get_tqdm

from akshare.datasets import get_ths_js


def _get_file_content_ths(file: str = "ths.js") -> str:
    """
    获取 JS 文件的内容
    :param file:  JS 文件名
    :type file: str
    :return: 文件内容
    :rtype: str
    """
    setting_file_path = get_ths_js(file)
    with open(setting_file_path, encoding="utf-8") as f:
        file_data = f.read()
    return file_data


def stock_fund_flow_individual(symbol: str = "即时") -> pd.DataFrame:
    """
    同花顺-数据中心-资金流向-个股资金流
    https://data.10jqka.com.cn/funds/ggzjl/#refCountId=data_55f13c2c_254
    :param symbol: choice of {“即时”, "3日排行", "5日排行", "10日排行", "20日排行"}
    :type symbol: str
    :return: 个股资金流
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "Accept": "text/html, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "hexin-v": v_code,
        "Host": "data.10jqka.com.cn",
        "Pragma": "no-cache",
        "Referer": "http://data.10jqka.com.cn/funds/hyzjl/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.85 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    url = "http://data.10jqka.com.cn/funds/ggzjl/field/code/order/desc/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    raw_page = soup.find(name="span", attrs={"class": "page_info"}).text
    page_num = raw_page.split("/")[1]
    if symbol == "3日排行":
        url = "http://data.10jqka.com.cn/funds/ggzjl/board/3/field/zdf/order/desc/page/{}/ajax/1/free/1/"
    elif symbol == "5日排行":
        url = "http://data.10jqka.com.cn/funds/ggzjl/board/5/field/zdf/order/desc/page/{}/ajax/1/free/1/"
    elif symbol == "10日排行":
        url = "http://data.10jqka.com.cn/funds/ggzjl/board/10/field/zdf/order/desc/page/{}/ajax/1/free/1/"
    elif symbol == "20日排行":
        url = "http://data.10jqka.com.cn/funds/ggzjl/board/20/field/zdf/order/desc/page/{}/ajax/1/free/1/"
    else:
        url = "http://data.10jqka.com.cn/funds/ggzjl/field/zdf/order/desc/page/{}/ajax/1/free/1/"
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(page_num) + 1), leave=False):
        js_code = py_mini_racer.MiniRacer()
        js_content = _get_file_content_ths("ths.js")
        js_code.eval(js_content)
        v_code = js_code.call("v")
        headers = {
            "Accept": "text/html, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "hexin-v": v_code,
            "Host": "data.10jqka.com.cn",
            "Pragma": "no-cache",
            "Referer": "http://data.10jqka.com.cn/funds/hyzjl/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.85 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }
        r = requests.get(url.format(page), headers=headers)
        temp_df = pd.read_html(StringIO(r.text))[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    del big_df["序号"]
    big_df.reset_index(inplace=True)
    big_df["index"] = range(1, len(big_df) + 1)
    if symbol == "即时":
        big_df.columns = [
            "序号",
            "股票代码",
            "股票简称",
            "最新价",
            "涨跌幅",
            "换手率",
            "流入资金",
            "流出资金",
            "净额",
            "成交额",
        ]
    else:
        big_df.columns = [
            "序号",
            "股票代码",
            "股票简称",
            "最新价",
            "阶段涨跌幅",
            "连续换手率",
            "资金流入净额",
        ]
    return big_df


def stock_fund_flow_concept(symbol: str = "即时") -> pd.DataFrame:
    """
    同花顺-数据中心-资金流向-概念资金流
    https://data.10jqka.com.cn/funds/gnzjl/#refCountId=data_55f13c2c_254
    :param symbol: choice of {“即时”, "3日排行", "5日排行", "10日排行", "20日排行"}
    :type symbol: str
    :return: 概念资金流
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "Accept": "text/html, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "hexin-v": v_code,
        "Host": "data.10jqka.com.cn",
        "Pragma": "no-cache",
        "Referer": "http://data.10jqka.com.cn/funds/gnzjl/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.85 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    url = (
        "http://data.10jqka.com.cn/funds/gnzjl/field/tradezdf/order/desc/ajax/1/free/1/"
    )
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    raw_page = soup.find(name="span", attrs={"class": "page_info"}).text
    page_num = raw_page.split("/")[1]
    if symbol == "3日排行":
        url = "http://data.10jqka.com.cn/funds/gnzjl/board/3/field/tradezdf/order/desc/page/{}/ajax/1/free/1/"
    elif symbol == "5日排行":
        url = "http://data.10jqka.com.cn/funds/gnzjl/board/5/field/tradezdf/order/desc/page/{}/ajax/1/free/1/"
    elif symbol == "10日排行":
        url = "http://data.10jqka.com.cn/funds/gnzjl/board/10/field/tradezdf/order/desc/page/{}/ajax/1/free/1/"
    elif symbol == "20日排行":
        url = "http://data.10jqka.com.cn/funds/gnzjl/board/20/field/tradezdf/order/desc/page/{}/ajax/1/free/1/"
    else:
        url = "http://data.10jqka.com.cn/funds/gnzjl/field/tradezdf/order/desc/page/{}/ajax/1/free/1/"
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(page_num) + 1), leave=False):
        js_code = py_mini_racer.MiniRacer()
        js_content = _get_file_content_ths("ths.js")
        js_code.eval(js_content)
        v_code = js_code.call("v")
        headers = {
            "Accept": "text/html, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "hexin-v": v_code,
            "Host": "data.10jqka.com.cn",
            "Pragma": "no-cache",
            "Referer": "http://data.10jqka.com.cn/funds/gnzjl/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.85 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }
        r = requests.get(url.format(page), headers=headers)
        temp_df = pd.read_html(StringIO(r.text))[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    del big_df["序号"]
    big_df.reset_index(inplace=True)
    big_df["index"] = range(1, len(big_df) + 1)
    if symbol == "即时":
        big_df.columns = [
            "序号",
            "行业",
            "行业指数",
            "行业-涨跌幅",
            "流入资金",
            "流出资金",
            "净额",
            "公司家数",
            "领涨股",
            "领涨股-涨跌幅",
            "当前价",
        ]
        big_df["行业-涨跌幅"] = big_df["行业-涨跌幅"].str.strip("%")
        big_df["领涨股-涨跌幅"] = big_df["领涨股-涨跌幅"].str.strip("%")
        big_df["行业-涨跌幅"] = pd.to_numeric(big_df["行业-涨跌幅"], errors="coerce")
        big_df["领涨股-涨跌幅"] = pd.to_numeric(
            big_df["领涨股-涨跌幅"], errors="coerce"
        )
    else:
        big_df.columns = [
            "序号",
            "行业",
            "公司家数",
            "行业指数",
            "阶段涨跌幅",
            "流入资金",
            "流出资金",
            "净额",
        ]
    return big_df


def stock_fund_flow_industry(symbol: str = "即时") -> pd.DataFrame:
    """
    同花顺-数据中心-资金流向-行业资金流
    https://data.10jqka.com.cn/funds/hyzjl/#refCountId=data_55f13c2c_254
    :param symbol: choice of {“即时”, "3日排行", "5日排行", "10日排行", "20日排行"}
    :type symbol: str
    :return: 行业资金流
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "Accept": "text/html, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "hexin-v": v_code,
        "Host": "data.10jqka.com.cn",
        "Pragma": "no-cache",
        "Referer": "http://data.10jqka.com.cn/funds/hyzjl/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.85 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    url = (
        "http://data.10jqka.com.cn/funds/hyzjl/field/tradezdf/order/desc/ajax/1/free/1/"
    )
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    raw_page = soup.find(name="span", attrs={"class": "page_info"}).text
    page_num = raw_page.split("/")[1]
    if symbol == "3日排行":
        url = "http://data.10jqka.com.cn/funds/hyzjl/board/3/field/tradezdf/order/desc/page/{}/ajax/1/free/1/"
    elif symbol == "5日排行":
        url = "http://data.10jqka.com.cn/funds/hyzjl/board/5/field/tradezdf/order/desc/page/{}/ajax/1/free/1/"
    elif symbol == "10日排行":
        url = "http://data.10jqka.com.cn/funds/hyzjl/board/10/field/tradezdf/order/desc/page/{}/ajax/1/free/1/"
    elif symbol == "20日排行":
        url = "http://data.10jqka.com.cn/funds/hyzjl/board/20/field/tradezdf/order/desc/page/{}/ajax/1/free/1/"
    else:
        url = "http://data.10jqka.com.cn/funds/hyzjl/field/tradezdf/order/desc/page/{}/ajax/1/free/1/"
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(page_num) + 1), leave=False):
        js_code = py_mini_racer.MiniRacer()
        js_content = _get_file_content_ths("ths.js")
        js_code.eval(js_content)
        v_code = js_code.call("v")
        headers = {
            "Accept": "text/html, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "hexin-v": v_code,
            "Host": "data.10jqka.com.cn",
            "Pragma": "no-cache",
            "Referer": "http://data.10jqka.com.cn/funds/hyzjl/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.85 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }
        r = requests.get(url.format(page), headers=headers)
        temp_df = pd.read_html(StringIO(r.text))[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    del big_df["序号"]
    big_df.reset_index(inplace=True)
    big_df["index"] = range(1, len(big_df) + 1)
    if symbol == "即时":
        big_df.columns = [
            "序号",
            "行业",
            "行业指数",
            "行业-涨跌幅",
            "流入资金",
            "流出资金",
            "净额",
            "公司家数",
            "领涨股",
            "领涨股-涨跌幅",
            "当前价",
        ]
        big_df["行业-涨跌幅"] = big_df["行业-涨跌幅"].str.strip("%")
        big_df["领涨股-涨跌幅"] = big_df["领涨股-涨跌幅"].str.strip("%")
        big_df["行业-涨跌幅"] = pd.to_numeric(big_df["行业-涨跌幅"], errors="coerce")
        big_df["领涨股-涨跌幅"] = pd.to_numeric(
            big_df["领涨股-涨跌幅"], errors="coerce"
        )
    else:
        big_df.columns = [
            "序号",
            "行业",
            "公司家数",
            "行业指数",
            "阶段涨跌幅",
            "流入资金",
            "流出资金",
            "净额",
        ]
    return big_df


def stock_fund_flow_big_deal() -> pd.DataFrame:
    """
    同花顺-数据中心-资金流向-大单追踪
    https://data.10jqka.com.cn/funds/ddzz
    :return: 大单追踪
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "Accept": "text/html, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "hexin-v": v_code,
        "Host": "data.10jqka.com.cn",
        "Pragma": "no-cache",
        "Referer": "http://data.10jqka.com.cn/funds/hyzjl/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.85 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    url = "http://data.10jqka.com.cn/funds/ddzz/order/desc/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    raw_page = soup.find(name="span", attrs={"class": "page_info"}).text
    page_num = raw_page.split("/")[1]
    url = "http://data.10jqka.com.cn/funds/ddzz/order/asc/page/{}/ajax/1/free/1/"
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(page_num) + 1), leave=False):
        js_code = py_mini_racer.MiniRacer()
        js_content = _get_file_content_ths("ths.js")
        js_code.eval(js_content)
        v_code = js_code.call("v")
        headers = {
            "Accept": "text/html, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "hexin-v": v_code,
            "Host": "data.10jqka.com.cn",
            "Pragma": "no-cache",
            "Referer": "http://data.10jqka.com.cn/funds/hyzjl/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.85 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }
        r = requests.get(url.format(page), headers=headers)
        temp_df = pd.read_html(StringIO(r.text))[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.columns = [
        "成交时间",
        "股票代码",
        "股票简称",
        "成交价格",
        "成交量",
        "成交额",
        "大单性质",
        "涨跌幅",
        "涨跌额",
        "详细",
    ]
    del big_df["详细"]
    return big_df


if __name__ == "__main__":
    # 同花顺-数据中心-资金流向-个股资金流
    stock_fund_flow_individual_df = stock_fund_flow_individual(symbol="即时")
    print(stock_fund_flow_individual_df)

    stock_fund_flow_individual_df = stock_fund_flow_individual(symbol="3日排行")
    print(stock_fund_flow_individual_df)

    stock_fund_flow_individual_df = stock_fund_flow_individual(symbol="5日排行")
    print(stock_fund_flow_individual_df)

    stock_fund_flow_individual_df = stock_fund_flow_individual(symbol="10日排行")
    print(stock_fund_flow_individual_df)

    stock_fund_flow_individual_df = stock_fund_flow_individual(symbol="20日排行")
    print(stock_fund_flow_individual_df)

    # 同花顺-数据中心-资金流向-概念资金流
    stock_fund_flow_concept_df = stock_fund_flow_concept(symbol="即时")
    print(stock_fund_flow_concept_df)

    stock_fund_flow_concept_df = stock_fund_flow_concept(symbol="3日排行")
    print(stock_fund_flow_concept_df)

    stock_fund_flow_concept_df = stock_fund_flow_concept(symbol="5日排行")
    print(stock_fund_flow_concept_df)

    stock_fund_flow_concept_df = stock_fund_flow_concept(symbol="10日排行")
    print(stock_fund_flow_concept_df)

    stock_fund_flow_concept_df = stock_fund_flow_concept(symbol="20日排行")
    print(stock_fund_flow_concept_df)

    # 同花顺-数据中心-资金流向-行业资金流
    stock_fund_flow_industry_df = stock_fund_flow_industry(symbol="即时")
    print(stock_fund_flow_industry_df)

    stock_fund_flow_industry_df = stock_fund_flow_industry(symbol="3日排行")
    print(stock_fund_flow_industry_df)

    stock_fund_flow_industry_df = stock_fund_flow_industry(symbol="5日排行")
    print(stock_fund_flow_industry_df)

    stock_fund_flow_industry_df = stock_fund_flow_industry(symbol="10日排行")
    print(stock_fund_flow_industry_df)

    stock_fund_flow_industry_df = stock_fund_flow_industry(symbol="20日排行")
    print(stock_fund_flow_industry_df)

    # 同花顺-数据中心-资金流向-大单追踪
    stock_fund_flow_big_deal_df = stock_fund_flow_big_deal()
    print(stock_fund_flow_big_deal_df)
