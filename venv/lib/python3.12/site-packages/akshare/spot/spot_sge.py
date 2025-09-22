# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2025/4/11 22:00
Desc: 上海黄金交易所-数据资讯-行情走势
https://www.sge.com.cn/sjzx/mrhq
上海黄金交易所-数据资讯-上海金基准价-历史数据
上海黄金交易所-数据资讯-上海银基准价-历史数据
"""

import pandas as pd
import requests

from akshare.utils.cons import headers


def spot_symbol_table_sge() -> pd.DataFrame:
    """
    上海黄金交易所-数据资讯-行情走势-品种表
    https://www.sge.com.cn/sjzx/mrhq
    :return: 品种表
    :rtype: pandas.DataFrame
    """
    temp_list = [
        "Au99.99",
        "Au99.95",
        "Au100g",
        "Pt99.95",
        "Ag(T+D)",
        "Au(T+D)",
        "mAu(T+D)",
        "Au(T+N1)",
        "Au(T+N2)",
        "Ag99.99",
        "iAu99.99",
        "Au99.5",
        "iAu100g",
        "iAu99.5",
        "PGC30g",
        "NYAuTN06",
        "NYAuTN12",
    ]
    temp_df = pd.DataFrame(temp_list)
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["序号", "品种"]
    temp_df["序号"] = temp_df["序号"] + 1
    return temp_df


def spot_quotations_sge(symbol: str = "Au99.99") -> pd.DataFrame:
    """
    上海黄金交易所-实时行情数据
    https://www.sge.com.cn/
    https://www.sge.com.cn/graph/quotations
    :param symbol: choice of {'Au99.99', 'Au99.95', 'Au100g', 'Pt99.95', 'Ag(T+D)', 'Au(T+D)',
    'mAu(T+D)', 'Au(T+N1)', 'Au(T+N2)', 'Ag99.99', 'iAu99.99', 'Au99.5', 'iAu100g',
    'iAu99.5', 'PGC30g', 'NYAuTN06', 'NYAuTN12'}; 可以通过 ak.spot_symbol_table_sge() 获取品种表
    :type symbol: str
    :return: 行情数据
    :rtype: pandas.DataFrame
    """
    url = "https://www.sge.com.cn/graph/quotations"
    payload = {"instid": symbol}
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": "15",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Host": "www.sge.com.cn",
        "Origin": "https://www.sge.com.cn",
        "Pragma": "no-cache",
        "Referer": "https://www.sge.com.cn/",
        "sec-ch-ua": '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.get(url, data=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(
        {
            "品种": data_json["heyue"],
            "时间": data_json["times"],
            "现价": data_json["data"],
            "更新时间": data_json["delaystr"],
        }
    )
    temp_df["现价"] = pd.to_numeric(temp_df["现价"], errors="coerce")
    # 将更新时间中的时间部分提取出来
    update_time = temp_df["更新时间"].iloc[0].split()[1]
    # 将时间列转换为时间格式以便排序
    temp_df["时间"] = pd.to_datetime(temp_df["时间"], format="%H:%M").dt.time
    # 过滤掉大于等于更新时间的数据
    temp_df = temp_df[temp_df["时间"].astype(str) < update_time]
    # 按时间排序
    temp_df = temp_df.sort_values(by=["时间"])
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


def spot_hist_sge(symbol: str = "Au99.99") -> pd.DataFrame:
    """
    上海黄金交易所-数据资讯-行情走势-历史数据
    https://www.sge.com.cn/sjzx/mrhq
    :param symbol: choice of {'Au99.99', 'Au99.95', 'Au100g', 'Pt99.95', 'Ag(T+D)', 'Au(T+D)',
    'mAu(T+D)', 'Au(T+N1)', 'Au(T+N2)', 'Ag99.99', 'iAu99.99', 'Au99.5', 'iAu100g', 'iAu99.5',
    'PGC30g', 'NYAuTN06', 'NYAuTN12'}; 可以通过 ak.spot_symbol_table_sge() 获取品种表
    :type symbol: str
    :return: 历史数据
    :rtype: pandas.DataFrame
    """
    url = "https://www.sge.com.cn/graph/Dailyhq"
    payload = {"instid": symbol}
    headers = {
        "Accept": "text/html, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": "15",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Host": "www.sge.com.cn",
        "Origin": "https://www.sge.com.cn",
        "Pragma": "no-cache",
        "Referer": "https://www.sge.com.cn/sjzx/mrhq",
        "sec-ch-ua": '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.post(url, data=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["time"])
    temp_df.columns = [
        "date",
        "open",
        "close",
        "low",
        "high",
    ]

    temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df["open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    temp_df["high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df["low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    return temp_df


def spot_golden_benchmark_sge() -> pd.DataFrame:
    """
    上海黄金交易所-数据资讯-上海金基准价-历史数据
    https://www.sge.com.cn/sjzx/jzj
    :return: 历史数据
    :rtype: pandas.DataFrame
    """
    url = "https://www.sge.com.cn/graph/DayilyJzj"
    payload = {}
    r = requests.post(url, data=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["wp"])
    temp_df.columns = [
        "交易时间",
        "晚盘价",
    ]
    temp_df["交易时间"] = pd.to_datetime(temp_df["交易时间"], unit="ms").dt.date
    temp_zp_df = pd.DataFrame(data_json["zp"])
    temp_zp_df.columns = [
        "交易时间",
        "早盘价",
    ]
    temp_zp_df["交易时间"] = pd.to_datetime(
        temp_zp_df["交易时间"], unit="ms", errors="coerce"
    ).dt.date
    temp_df["早盘价"] = temp_zp_df["早盘价"]
    temp_df["晚盘价"] = pd.to_numeric(temp_df["晚盘价"], errors="coerce")
    temp_df["早盘价"] = pd.to_numeric(temp_df["早盘价"], errors="coerce")
    return temp_df


def spot_silver_benchmark_sge() -> pd.DataFrame:
    """
    上海黄金交易所-数据资讯-上海银基准价-历史数据
    https://www.sge.com.cn/sjzx/mrhq
    :return: 历史数据
    :rtype: pandas.DataFrame
    """
    url = "https://www.sge.com.cn/graph/DayilyShsilverJzj"
    payload = {}
    r = requests.post(url, data=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["wp"])
    temp_df.columns = [
        "交易时间",
        "晚盘价",
    ]
    temp_df["交易时间"] = pd.to_datetime(temp_df["交易时间"], unit="ms").dt.date
    temp_zp_df = pd.DataFrame(data_json["zp"])
    temp_zp_df.columns = [
        "交易时间",
        "早盘价",
    ]
    temp_zp_df["交易时间"] = pd.to_datetime(
        temp_zp_df["交易时间"], unit="ms", errors="coerce"
    ).dt.date
    temp_df["早盘价"] = temp_zp_df["早盘价"]
    temp_df["晚盘价"] = pd.to_numeric(temp_df["晚盘价"], errors="coerce")
    temp_df["早盘价"] = pd.to_numeric(temp_df["早盘价"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    spot_symbol_table_sge_df = spot_symbol_table_sge()
    print(spot_symbol_table_sge_df)

    spot_hist_sge_df = spot_hist_sge(symbol="Au99.99")
    print(spot_hist_sge_df)

    spot_golden_benchmark_sge_df = spot_golden_benchmark_sge()
    print(spot_golden_benchmark_sge_df)

    spot_silver_benchmark_sge_df = spot_silver_benchmark_sge()
    print(spot_silver_benchmark_sge_df)

    for spot in spot_symbol_table_sge_df["品种"].tolist():
        spot_hist_sge_df = spot_hist_sge(symbol=spot)
        print(spot_hist_sge_df)

    spot_quotations_sge_df = spot_quotations_sge(symbol="Au99.99")
    print(spot_quotations_sge_df)
