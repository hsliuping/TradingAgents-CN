#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/27 14:20
Desc: 同花顺-板块-概念板块
https://q.10jqka.com.cn/thshy/
"""

from typing import Dict
from datetime import datetime
from functools import lru_cache
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup
import py_mini_racer

from akshare.datasets import get_ths_js
from akshare.utils import demjson
from akshare.utils.tqdm import get_tqdm


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


@lru_cache()
def _get_stock_board_concept_name_ths() -> dict:
    """
    获取同花顺概念板块代码和名称字典
    :return: 获取同花顺概念板块代码和名称字典
    :rtype: dict
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "https://q.10jqka.com.cn/gn/detail/code/307822/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    code_list = [
        item["href"].split("/")[-2]
        for item in soup.find(name="div", attrs={"class": "cate_inner"}).find_all("a")
    ]
    name_list = [
        item.text
        for item in soup.find(name="div", attrs={"class": "cate_inner"}).find_all("a")
    ]
    name_code_map = dict(zip(name_list, code_list))
    temp_dict = __stock_board_concept_summary_ths()
    name_code_map.update(temp_dict)
    return name_code_map


def stock_board_concept_name_ths() -> pd.DataFrame:
    """
    同花顺-板块-概念板块-概念
    http://q.10jqka.com.cn/thshy/
    :return: 所有概念板块的名称和链接
    :rtype: pandas.DataFrame
    """
    code_name_ths_map = _get_stock_board_concept_name_ths()
    temp_df = pd.DataFrame.from_dict(code_name_ths_map, orient="index")
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["name", "code"]
    temp_df = temp_df[
        [
            "name",
            "code",
        ]
    ]
    return temp_df


def stock_board_concept_info_ths(symbol: str = "阿里巴巴概念") -> pd.DataFrame:
    """
    同花顺-板块-概念板块-板块简介
    http://q.10jqka.com.cn/gn/detail/code/301558/
    :param symbol: 板块简介
    :type symbol: str
    :return: 板块简介
    :rtype: pandas.DataFrame
    """
    stock_board_ths_map_df = stock_board_concept_name_ths()
    symbol_code = stock_board_ths_map_df[stock_board_ths_map_df["name"] == symbol][
        "code"
    ].values[0]
    url = f"http://q.10jqka.com.cn/gn/detail/code/{symbol_code}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/89.0.4389.90 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    name_list = [
        item.text.strip()
        for item in soup.find(name="div", attrs={"class": "board-infos"}).find_all("dt")
    ]
    value_list = [
        item.text.strip().replace("\n", "/")
        for item in soup.find(name="div", attrs={"class": "board-infos"}).find_all("dd")
    ]
    temp_df = pd.DataFrame([name_list, value_list]).T
    temp_df.columns = ["项目", "值"]
    return temp_df


def stock_board_concept_index_ths(
    symbol: str = "阿里巴巴概念",
    start_date: str = "20200101",
    end_date: str = "20250228",
) -> pd.DataFrame:
    """
    同花顺-板块-概念板块-指数数据
    https://q.10jqka.com.cn/gn/detail/code/301558/
    :param start_date: 开始时间
    :type start_date: str
    :param end_date: 结束时间
    :type end_date: str
    :param symbol: 指数数据
    :type symbol: str
    :return: 指数数据
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")

    code_map = _get_stock_board_concept_name_ths()
    symbol_code = code_map[symbol]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/89.0.4389.90 Safari/537.36",
    }
    url = f"https://q.10jqka.com.cn/gn/detail/code/{symbol_code}"
    r = requests.get(url=url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    inner_code = soup.find(name="input", attrs={"id": "clid"})["value"]
    big_df = pd.DataFrame()
    current_year = datetime.now().year
    begin_year = int(start_date[:4])
    tqdm = get_tqdm()
    for year in tqdm(range(begin_year, current_year + 1), leave=False):
        url = f"https://d.10jqka.com.cn/v4/line/bk_{inner_code}/01/{year}.js"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/89.0.4389.90 Safari/537.36",
            "Referer": "http://q.10jqka.com.cn",
            "Host": "d.10jqka.com.cn",
            "Cookie": f"v={v_code}",
        }
        r = requests.get(url, headers=headers)
        data_text = r.text

        try:
            demjson.decode(data_text[data_text.find("{") : -1])
        except:  # noqa: E722
            continue
        temp_df = demjson.decode(data_text[data_text.find("{") : -1])
        temp_df = pd.DataFrame(temp_df["data"].split(";"))
        temp_df = temp_df.iloc[:, 0].str.split(",", expand=True)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    if len(big_df.columns) == 11:
        big_df.columns = [
            "日期",
            "开盘价",
            "最高价",
            "最低价",
            "收盘价",
            "成交量",
            "成交额",
            "_",
            "_",
            "_",
            "_",
        ]
    else:
        big_df.columns = [
            "日期",
            "开盘价",
            "最高价",
            "最低价",
            "收盘价",
            "成交量",
            "成交额",
            "_",
            "_",
            "_",
            "_",
            "_",
        ]
    big_df = big_df[
        [
            "日期",
            "开盘价",
            "最高价",
            "最低价",
            "收盘价",
            "成交量",
            "成交额",
        ]
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df.index = pd.to_datetime(big_df["日期"], errors="coerce")
    big_df = big_df[start_date:end_date]
    big_df.reset_index(drop=True, inplace=True)
    big_df["开盘价"] = pd.to_numeric(big_df["开盘价"], errors="coerce")
    big_df["最高价"] = pd.to_numeric(big_df["最高价"], errors="coerce")
    big_df["最低价"] = pd.to_numeric(big_df["最低价"], errors="coerce")
    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["成交额"] = pd.to_numeric(big_df["成交额"], errors="coerce")
    return big_df


@lru_cache()
def __stock_board_concept_summary_ths() -> Dict:
    """
    同花顺-数据中心-概念板块-概念时间表-辅助函数
    https://q.10jqka.com.cn/gn/
    :return: 概念时间表
    :rtype: dict
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/1/ajax/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    page_num = soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1]
    big_dict = dict()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(page_num) + 1), leave=False):
        url = f"http://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/{page}/ajax/1/"
        r = requests.get(url, headers=headers)
        try:
            soup = BeautifulSoup(r.text, features="lxml")
            temp_dict = {
                item.get_text(): item["href"].rsplit("/")[-2]
                for item in soup.find_all(name="a")
                if "detail" in item["href"]
            }
            big_dict.update(temp_dict)
        except ValueError:
            break
    return big_dict


def stock_board_concept_summary_ths() -> pd.DataFrame:
    """
    同花顺-数据中心-概念板块-概念时间表
    https://q.10jqka.com.cn/gn/
    :return: 概念时间表
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/1/ajax/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    page_num = soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(page_num) + 1), leave=False):
        url = f"http://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/{page}/ajax/1/"
        r = requests.get(url, headers=headers)
        try:
            temp_df = pd.read_html(StringIO(r.text))[0]
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
        except ValueError:
            break
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["成分股数量"] = pd.to_numeric(big_df["成分股数量"], errors="coerce")
    return big_df


if __name__ == "__main__":
    stock_board_concept_name_ths_df = stock_board_concept_name_ths()
    print(stock_board_concept_name_ths_df)

    stock_board_concept_info_ths_df = stock_board_concept_info_ths(
        symbol="阿里巴巴概念"
    )
    print(stock_board_concept_info_ths_df)

    stock_board_concept_index_ths_df = stock_board_concept_index_ths(
        symbol="DeepSeek概念", start_date="20200101", end_date="20250321"
    )
    print(stock_board_concept_index_ths_df)

    stock_board_concept_summary_ths_df = stock_board_concept_summary_ths()
    print(stock_board_concept_summary_ths_df)

    for stock in stock_board_concept_name_ths_df["name"]:
        print(stock)
        stock_board_industry_index_ths_df = stock_board_concept_index_ths(symbol=stock)
        print(stock_board_industry_index_ths_df)
