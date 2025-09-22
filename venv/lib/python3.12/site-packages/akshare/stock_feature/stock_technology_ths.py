# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/9/21 19:00
Desc: 同花顺-数据中心-技术选股
https://data.10jqka.com.cn/rank/cxg/
"""

from io import StringIO

import pandas as pd
import py_mini_racer
import requests
from bs4 import BeautifulSoup

from akshare.datasets import get_ths_js
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


def stock_rank_cxg_ths(symbol: str = "创月新高") -> pd.DataFrame:
    """
    同花顺-数据中心-技术选股-创新高
    https://data.10jqka.com.cn/rank/cxg/
    :param symbol: choice of {"创月新高", "半年新高", "一年新高", "历史新高"}
    :type symbol: str
    :return: 创新高数据
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "创月新高": "4",
        "半年新高": "3",
        "一年新高": "2",
        "历史新高": "1",
    }
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = (
        f"http://data.10jqka.com.cn/rank/cxg/board/{symbol_map[symbol]}/field/"
        f"stockcode/order/asc/page/1/ajax/1/free/1/"
    )
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = soup.find(name="span", attrs={"class": "page_info"}).text.split(
            "/"
        )[1]
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        v_code = js_code.call("v")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
            "Cookie": f"v={v_code}",
        }
        url = (
            f"http://data.10jqka.com.cn/rank/cxg/board/{symbol_map[symbol]}/field/stockcode/"
            f"order/asc/page/{page}/ajax/1/free/1/"
        )
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text))[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "涨跌幅",
        "换手率",
        "最新价",
        "前期高点",
        "前期高点日期",
    ]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].str.strip("%")
    big_df["换手率"] = big_df["换手率"].str.strip("%")
    big_df["前期高点日期"] = pd.to_datetime(
        big_df["前期高点日期"], errors="coerce"
    ).dt.date
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["前期高点"] = pd.to_numeric(big_df["前期高点"], errors="coerce")
    return big_df


def stock_rank_cxd_ths(symbol: str = "创月新低") -> pd.DataFrame:
    """
    同花顺-数据中心-技术选股-创新低
    https://data.10jqka.com.cn/rank/cxd/
    :param symbol: choice of {"创月新低", "半年新低", "一年新低", "历史新低"}
    :type symbol: str
    :return: 创新低数据
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "创月新低": "4",
        "半年新低": "3",
        "一年新低": "2",
        "历史新低": "1",
    }
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = (
        f"http://data.10jqka.com.cn/rank/cxd/board/{symbol_map[symbol]}/field/"
        f"stockcode/order/asc/page/1/ajax/1/free/1/"
    )
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = soup.find(name="span", attrs={"class": "page_info"}).text.split(
            "/"
        )[1]
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        v_code = js_code.call("v")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
            "Cookie": f"v={v_code}",
        }
        url = (
            f"http://data.10jqka.com.cn/rank/cxd/board/{symbol_map[symbol]}/field/"
            f"stockcode/order/asc/page/{page}/ajax/1/free/1/"
        )
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text))[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "涨跌幅",
        "换手率",
        "最新价",
        "前期低点",
        "前期低点日期",
    ]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].str.strip("%")
    big_df["换手率"] = big_df["换手率"].str.strip("%")
    big_df["前期低点日期"] = pd.to_datetime(
        big_df["前期低点日期"], errors="coerce"
    ).dt.date
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["前期低点"] = pd.to_numeric(big_df["前期低点"], errors="coerce")
    return big_df


def stock_rank_lxsz_ths() -> pd.DataFrame:
    """
    同花顺-数据中心-技术选股-连续上涨
    https://data.10jqka.com.cn/rank/lxsz/
    :return: 连续上涨
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/lxsz/field/lxts/order/desc/page/1/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = soup.find(name="span", attrs={"class": "page_info"}).text.split(
            "/"
        )[1]
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        v_code = js_code.call("v")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
            "Cookie": f"v={v_code}",
        }
        url = f"http://data.10jqka.com.cn/rank/lxsz/field/lxts/order/desc/page/{page}/ajax/1/free/1/"
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "收盘价",
        "最高价",
        "最低价",
        "连涨天数",
        "连续涨跌幅",
        "累计换手率",
        "所属行业",
    ]
    big_df["连续涨跌幅"] = big_df["连续涨跌幅"].str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].str.strip("%")
    big_df["连续涨跌幅"] = pd.to_numeric(big_df["连续涨跌幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["最高价"] = pd.to_numeric(big_df["最高价"], errors="coerce")
    big_df["最低价"] = pd.to_numeric(big_df["最低价"], errors="coerce")
    big_df["连涨天数"] = pd.to_numeric(big_df["连涨天数"], errors="coerce")
    return big_df


def stock_rank_lxxd_ths() -> pd.DataFrame:
    """
    同花顺-数据中心-技术选股-连续下跌
    https://data.10jqka.com.cn/rank/lxxd/
    :return: 连续下跌
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/lxxd/field/lxts/order/desc/page/1/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = soup.find(name="span", attrs={"class": "page_info"}).text.split(
            "/"
        )[1]
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        v_code = js_code.call("v")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
            "Cookie": f"v={v_code}",
        }
        url = f"http://data.10jqka.com.cn/rank/lxxd/field/lxts/order/desc/page/{page}/ajax/1/free/1/"
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "收盘价",
        "最高价",
        "最低价",
        "连涨天数",
        "连续涨跌幅",
        "累计换手率",
        "所属行业",
    ]
    big_df["连续涨跌幅"] = big_df["连续涨跌幅"].str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].str.strip("%")
    big_df["连续涨跌幅"] = pd.to_numeric(big_df["连续涨跌幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["最高价"] = pd.to_numeric(big_df["最高价"], errors="coerce")
    big_df["最低价"] = pd.to_numeric(big_df["最低价"], errors="coerce")
    big_df["连涨天数"] = pd.to_numeric(big_df["连涨天数"], errors="coerce")
    return big_df


def stock_rank_cxfl_ths() -> pd.DataFrame:
    """
    同花顺-数据中心-技术选股-持续放量
    https://data.10jqka.com.cn/rank/cxfl/
    :return: 持续放量
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/cxfl/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = soup.find(name="span", attrs={"class": "page_info"}).text.split(
            "/"
        )[1]
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        v_code = js_code.call("v")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
            "Cookie": f"v={v_code}",
        }
        url = f"http://data.10jqka.com.cn/rank/cxfl/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "涨跌幅",
        "最新价",
        "成交量",
        "基准日成交量",
        "放量天数",
        "阶段涨跌幅",
        "所属行业",
    ]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["阶段涨跌幅"] = big_df["阶段涨跌幅"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["阶段涨跌幅"] = pd.to_numeric(big_df["阶段涨跌幅"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["放量天数"] = pd.to_numeric(big_df["放量天数"], errors="coerce")
    return big_df


def stock_rank_cxsl_ths() -> pd.DataFrame:
    """
    同花顺-数据中心-技术选股-持续缩量
    https://data.10jqka.com.cn/rank/cxsl/
    :return: 持续缩量
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/cxsl/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = soup.find(name="span", attrs={"class": "page_info"}).text.split(
            "/"
        )[1]
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        v_code = js_code.call("v")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
            "Cookie": f"v={v_code}",
        }
        url = f"http://data.10jqka.com.cn/rank/cxsl/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "涨跌幅",
        "最新价",
        "成交量",
        "基准日成交量",
        "缩量天数",
        "阶段涨跌幅",
        "所属行业",
    ]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["阶段涨跌幅"] = big_df["阶段涨跌幅"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["阶段涨跌幅"] = pd.to_numeric(big_df["阶段涨跌幅"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["缩量天数"] = pd.to_numeric(big_df["缩量天数"], errors="coerce")
    return big_df


def stock_rank_xstp_ths(symbol: str = "500日均线") -> pd.DataFrame:
    """
    同花顺-数据中心-技术选股-向上突破
    http://data.10jqka.com.cn/rank/xstp/
    :param symbol: choice of {"5日均线", "10日均线", "20日均线", "30日均线", "60日均线", "90日均线", "250日均线", "500日均线"}
    :type symbol: str
    :return: 向上突破
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "5日均线": 5,
        "10日均线": 10,
        "20日均线": 20,
        "30日均线": 30,
        "60日均线": 60,
        "90日均线": 90,
        "250日均线": 250,
        "500日均线": 500,
    }
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = f"http://data.10jqka.com.cn/rank/xstp/board/{symbol_map[symbol]}/order/asc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = soup.find(name="span", attrs={"class": "page_info"}).text.split(
            "/"
        )[1]
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        v_code = js_code.call("v")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
            "Cookie": f"v={v_code}",
        }
        url = (
            f"http://data.10jqka.com.cn/rank/xstp/board/{symbol_map[symbol]}/order/"
            f"asc/ajax/1/free/1/page/{page}/free/1/"
        )
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "最新价",
        "成交额",
        "成交量",
        "涨跌幅",
        "换手率",
    ]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["换手率"] = big_df["换手率"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    return big_df


def stock_rank_xxtp_ths(symbol: str = "500日均线") -> pd.DataFrame:
    """
    同花顺-数据中心-技术选股-向下突破
    https://data.10jqka.com.cn/rank/xxtp/
    :param symbol: choice of {"5日均线", "10日均线", "20日均线", "30日均线", "60日均线", "90日均线", "250日均线", "500日均线"}
    :type symbol: str
    :return: 向下突破
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "5日均线": 5,
        "10日均线": 10,
        "20日均线": 20,
        "30日均线": 30,
        "60日均线": 60,
        "90日均线": 90,
        "250日均线": 250,
        "500日均线": 500,
    }
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = f"http://data.10jqka.com.cn/rank/xxtp/board/{symbol_map[symbol]}/order/asc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = soup.find(name="span", attrs={"class": "page_info"}).text.split(
            "/"
        )[1]
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        v_code = js_code.call("v")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
            "Cookie": f"v={v_code}",
        }
        url = (
            f"http://data.10jqka.com.cn/rank/xxtp/board/{symbol_map[symbol]}/order/"
            f"asc/ajax/1/free/1/page/{page}/free/1/"
        )
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "最新价",
        "成交额",
        "成交量",
        "涨跌幅",
        "换手率",
    ]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["换手率"] = big_df["换手率"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    return big_df


def stock_rank_ljqs_ths() -> pd.DataFrame:
    """
    同花顺-数据中心-技术选股-量价齐升
    http://data.10jqka.com.cn/rank/ljqs/
    :return: 量价齐升
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/ljqs/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = soup.find(name="span", attrs={"class": "page_info"}).text.split(
            "/"
        )[1]
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        v_code = js_code.call("v")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
            "Cookie": f"v={v_code}",
        }
        url = f"http://data.10jqka.com.cn/rank/ljqs/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "最新价",
        "量价齐升天数",
        "阶段涨幅",
        "累计换手率",
        "所属行业",
    ]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["阶段涨幅"] = big_df["阶段涨幅"].astype(str).str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].astype(str).str.strip("%")
    big_df["阶段涨幅"] = pd.to_numeric(big_df["阶段涨幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["量价齐升天数"] = pd.to_numeric(big_df["量价齐升天数"], errors="coerce")
    return big_df


def stock_rank_ljqd_ths() -> pd.DataFrame:
    """
    同花顺-数据中心-技术选股-量价齐跌
    http://data.10jqka.com.cn/rank/ljqd/
    :return: 量价齐跌
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/ljqd/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = soup.find(name="span", attrs={"class": "page_info"}).text.split(
            "/"
        )[1]
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        v_code = js_code.call("v")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
            "Cookie": f"v={v_code}",
        }
        url = f"http://data.10jqka.com.cn/rank/ljqd/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "最新价",
        "量价齐跌天数",
        "阶段涨幅",
        "累计换手率",
        "所属行业",
    ]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["阶段涨幅"] = big_df["阶段涨幅"].astype(str).str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].astype(str).str.strip("%")
    big_df["阶段涨幅"] = pd.to_numeric(big_df["阶段涨幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["量价齐跌天数"] = pd.to_numeric(big_df["量价齐跌天数"], errors="coerce")
    return big_df


def stock_rank_xzjp_ths() -> pd.DataFrame:
    """
    同花顺-数据中心-技术选股-险资举牌
    https://data.10jqka.com.cn/financial/xzjp/
    :return: 险资举牌
    :rtype: pandas.DataFrame
    """
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    big_df = pd.DataFrame()
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/ajax/xzjp/field/DECLAREDATE/order/desc/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
    big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "序号",
        "举牌公告日",
        "股票代码",
        "股票简称",
        "现价",
        "涨跌幅",
        "举牌方",
        "增持数量",
        "交易均价",
        "增持数量占总股本比例",
        "变动后持股总数",
        "变动后持股比例",
        "历史数据",
    ]
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.zfill(6)
    big_df["增持数量占总股本比例"] = (
        big_df["增持数量占总股本比例"].astype(str).str.strip("%")
    )
    big_df["变动后持股比例"] = big_df["变动后持股比例"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["增持数量占总股本比例"] = pd.to_numeric(
        big_df["增持数量占总股本比例"], errors="coerce"
    )
    big_df["变动后持股比例"] = pd.to_numeric(big_df["变动后持股比例"], errors="coerce")
    big_df["举牌公告日"] = pd.to_datetime(big_df["举牌公告日"], errors="coerce").dt.date
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["现价"] = pd.to_numeric(big_df["现价"], errors="coerce")
    big_df["交易均价"] = pd.to_numeric(big_df["交易均价"], errors="coerce")
    del big_df["历史数据"]
    return big_df


if __name__ == "__main__":
    stock_rank_cxg_ths_df = stock_rank_cxg_ths(symbol="创月新高")
    print(stock_rank_cxg_ths_df)

    stock_rank_cxg_ths_df = stock_rank_cxg_ths(symbol="半年新高")
    print(stock_rank_cxg_ths_df)

    stock_rank_cxg_ths_df = stock_rank_cxg_ths(symbol="一年新高")
    print(stock_rank_cxg_ths_df)

    stock_rank_cxg_ths_df = stock_rank_cxg_ths(symbol="历史新高")
    print(stock_rank_cxg_ths_df)

    stock_rank_cxd_ths_df = stock_rank_cxd_ths(symbol="创月新低")
    print(stock_rank_cxd_ths_df)

    stock_rank_cxd_ths_df = stock_rank_cxd_ths(symbol="半年新低")
    print(stock_rank_cxd_ths_df)

    stock_rank_cxd_ths_df = stock_rank_cxd_ths(symbol="一年新低")
    print(stock_rank_cxd_ths_df)

    stock_rank_cxd_ths_df = stock_rank_cxd_ths(symbol="历史新低")
    print(stock_rank_cxd_ths_df)

    stock_rank_lxsz_ths_df = stock_rank_lxsz_ths()
    print(stock_rank_lxsz_ths_df)

    stock_rank_lxxd_ths_df = stock_rank_lxxd_ths()
    print(stock_rank_lxxd_ths_df)

    stock_rank_cxfl_ths_df = stock_rank_cxfl_ths()
    print(stock_rank_cxfl_ths_df)

    stock_rank_cxsl_ths_df = stock_rank_cxsl_ths()
    print(stock_rank_cxsl_ths_df)

    stock_rank_xstp_ths_df = stock_rank_xstp_ths(symbol="500日均线")
    print(stock_rank_xstp_ths_df)

    stock_rank_xxtp_ths_df = stock_rank_xxtp_ths(symbol="500日均线")
    print(stock_rank_xxtp_ths_df)

    stock_rank_ljqs_ths_df = stock_rank_ljqs_ths()
    print(stock_rank_ljqs_ths_df)

    stock_rank_ljqd_ths_df = stock_rank_ljqd_ths()
    print(stock_rank_ljqd_ths_df)

    stock_rank_xzjp_ths_df = stock_rank_xzjp_ths()
    print(stock_rank_xzjp_ths_df)
