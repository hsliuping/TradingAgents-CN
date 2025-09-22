#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/22 18:00
Desc: 东方财富网-数据中心-资金流向-排名
https://data.eastmoney.com/zjlx/detail.html
异步接口-测试版
"""

import asyncio
from typing import Dict, List

import aiohttp
import pandas as pd


async def fetch_single_page(
    session: aiohttp.ClientSession, url: str, params: Dict
) -> Dict:
    """异步获取单页数据"""
    async with session.get(url, params=params, ssl=False) as response:
        return await response.json()


async def fetch_all_pages_async(url: str, base_params: Dict) -> List[Dict]:
    """异步获取所有页面数据"""
    # 首先获取总数以计算页数
    first_page_params = base_params.copy()
    first_page_params["pn"] = "1"

    async with aiohttp.ClientSession() as session:
        first_page_data = await fetch_single_page(session, url, first_page_params)

        # 检查是否成功获取数据
        if first_page_data.get("rc") != 0 or not first_page_data.get("data"):
            return [first_page_data]  # 返回错误信息

        total = first_page_data["data"]["total"]
        page_size = int(base_params["pz"])
        total_pages = (total + page_size - 1) // page_size

        # 限制页数，避免过大请求
        total_pages = min(total_pages, 100)

        # 创建所有页面的任务
        tasks = []
        for page in range(1, total_pages + 1):
            page_params = base_params.copy()
            page_params["pn"] = str(page)
            tasks.append(fetch_single_page(session, url, page_params))

        # 并发执行所有任务
        results = await asyncio.gather(*tasks)
        return results


def process_fund_flow_data(page_results: List[Dict], indicator: str) -> pd.DataFrame:
    """处理资金流向排名数据，转换为DataFrame"""
    all_data = []

    for result in page_results:
        if result.get("data") and result["data"].get("diff"):
            page_data = result["data"]["diff"]
            all_data.extend(page_data)

    if not all_data:
        return pd.DataFrame()

    temp_df = pd.DataFrame(all_data)

    # 根据不同的指标设置列名并选择需要的列
    if indicator == "今日":
        columns_map = {
            "f12": "代码",
            "f14": "名称",
            "f2": "最新价",
            "f3": "今日涨跌幅",
            "f62": "今日主力净流入-净额",
            "f184": "今日主力净流入-净占比",
            "f66": "今日超大单净流入-净额",
            "f69": "今日超大单净流入-净占比",
            "f72": "今日大单净流入-净额",
            "f75": "今日大单净流入-净占比",
            "f78": "今日中单净流入-净额",
            "f81": "今日中单净流入-净占比",
            "f84": "今日小单净流入-净额",
            "f87": "今日小单净流入-净占比",
        }
        main_column = "f62"  # 今日主力净流入-净额

    elif indicator == "3日":
        columns_map = {
            "f12": "代码",
            "f14": "名称",
            "f2": "最新价",
            "f127": "3日涨跌幅",
            "f267": "3日主力净流入-净额",
            "f268": "3日主力净流入-净占比",
            "f269": "3日超大单净流入-净额",
            "f270": "3日超大单净流入-净占比",
            "f271": "3日大单净流入-净额",
            "f272": "3日大单净流入-净占比",
            "f273": "3日中单净流入-净额",
            "f274": "3日中单净流入-净占比",
            "f275": "3日小单净流入-净额",
            "f276": "3日小单净流入-净占比",
        }
        main_column = "f267"  # 3日主力净流入-净额

    elif indicator == "5日":
        columns_map = {
            "f12": "代码",
            "f14": "名称",
            "f2": "最新价",
            "f109": "5日涨跌幅",
            "f164": "5日主力净流入-净额",
            "f165": "5日主力净流入-净占比",
            "f166": "5日超大单净流入-净额",
            "f167": "5日超大单净流入-净占比",
            "f168": "5日大单净流入-净额",
            "f169": "5日大单净流入-净占比",
            "f170": "5日中单净流入-净额",
            "f171": "5日中单净流入-净占比",
            "f172": "5日小单净流入-净额",
            "f173": "5日小单净流入-净占比",
        }
        main_column = "f164"  # 5日主力净流入-净额

    elif indicator == "10日":
        columns_map = {
            "f12": "代码",
            "f14": "名称",
            "f2": "最新价",
            "f160": "10日涨跌幅",
            "f174": "10日主力净流入-净额",
            "f175": "10日主力净流入-净占比",
            "f176": "10日超大单净流入-净额",
            "f177": "10日超大单净流入-净占比",
            "f178": "10日大单净流入-净额",
            "f179": "10日大单净流入-净占比",
            "f180": "10日中单净流入-净额",
            "f181": "10日中单净流入-净占比",
            "f182": "10日小单净流入-净额",
            "f183": "10日小单净流入-净占比",
        }
        main_column = "f174"  # 10日主力净流入-净额

    # 确保数值型列为数值类型
    numeric_columns = [
        col
        for col in temp_df.columns
        if col.startswith("f") and col not in ["f12", "f14"]
    ]
    for col in numeric_columns:
        if col in temp_df.columns:
            temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")

    # 按照主力净流入额降序排序
    if main_column in temp_df.columns:
        temp_df.sort_values(by=main_column, ascending=False, inplace=True)

    # 首先重命名列
    temp_df.rename(columns=columns_map, inplace=True)

    # 选择需要的列
    selected_columns = list(columns_map.values())
    available_columns = [col for col in selected_columns if col in temp_df.columns]
    temp_df = temp_df[available_columns]

    # 重置索引并生成序号列
    temp_df.reset_index(drop=True, inplace=True)
    temp_df.insert(0, "序号", range(1, len(temp_df) + 1))

    return temp_df


async def stock_individual_fund_flow_rank_async(indicator: str = "5日") -> pd.DataFrame:
    """
    异步获取东方财富网-数据中心-资金流向-排名
    https://data.eastmoney.com/zjlx/detail.html
    :param indicator: choice of {"今日", "3日", "5日", "10日"}
    :type indicator: str
    :return: 指定 indicator 资金流向排行
    :rtype: pandas.DataFrame
    """
    indicator_map = {
        "今日": [
            "f62",
            "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124",
        ],
        "3日": [
            "f267",
            "f12,f14,f2,f127,f267,f268,f269,f270,f271,f272,f273,f274,f275,f276,f257,f258,f124",
        ],
        "5日": [
            "f164",
            "f12,f14,f2,f109,f164,f165,f166,f167,f168,f169,f170,f171,f172,f173,f257,f258,f124",
        ],
        "10日": [
            "f174",
            "f12,f14,f2,f160,f174,f175,f176,f177,f178,f179,f180,f181,f182,f183,f260,f261,f124",
        ],
    }

    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "fid": indicator_map[indicator][0],
        "po": "1",  # 按照降序排列
        "pz": "100",  # 每页100条
        "pn": "1",  # 从第1页开始
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fs": "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2",
        "fields": indicator_map[indicator][1],
    }

    results = await fetch_all_pages_async(url, params)
    return process_fund_flow_data(results, indicator)


def stock_individual_fund_flow_rank(indicator: str = "5日") -> pd.DataFrame:
    """
    东方财富网-数据中心-资金流向-排名 (同步接口)
    https://data.eastmoney.com/zjlx/detail.html
    :param indicator: choice of {"今日", "3日", "5日", "10日"}
    :type indicator: str
    :return: 指定 indicator 资金流向排行
    :rtype: pandas.DataFrame
    """
    import nest_asyncio

    nest_asyncio.apply()
    return asyncio.run(stock_individual_fund_flow_rank_async(indicator))


if __name__ == "__main__":
    # 测试同步接口
    stock_individual_fund_flow_rank_df = stock_individual_fund_flow_rank(
        indicator="今日"
    )
    print(stock_individual_fund_flow_rank_df)

    stock_individual_fund_flow_rank_df = stock_individual_fund_flow_rank(
        indicator="3日"
    )
    print(stock_individual_fund_flow_rank_df)

    stock_individual_fund_flow_rank_df = stock_individual_fund_flow_rank(
        indicator="5日"
    )
    print(stock_individual_fund_flow_rank_df)

    stock_individual_fund_flow_rank_df = stock_individual_fund_flow_rank(
        indicator="10日"
    )
    print(stock_individual_fund_flow_rank_df)
