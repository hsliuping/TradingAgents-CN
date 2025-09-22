#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/22 18:00
Desc: 东方财富网-行情中心-沪深京板块-概念板块-名称
https://quote.eastmoney.com/center/boardlist.html#concept_board
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


def process_concept_board_data(page_results: List[Dict]) -> pd.DataFrame:
    """处理概念板块数据，转换为DataFrame"""
    all_data = []

    for result in page_results:
        if result.get("data") and result["data"].get("diff"):
            page_data = result["data"]["diff"]
            all_data.extend(page_data)

    if not all_data:
        return pd.DataFrame()

    temp_df = pd.DataFrame(all_data)

    # 转换数值类型，确保排序正确
    numeric_columns = ["f2", "f3", "f4", "f8", "f20", "f104", "f105", "f136"]
    for col in numeric_columns:
        if col in temp_df.columns:
            temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")

    # 按涨跌幅(f3)降序排序
    if "f3" in temp_df.columns:
        temp_df.sort_values(by="f3", ascending=False, inplace=True)

    # 重命名列
    columns_map = {
        "f2": "最新价",
        "f3": "涨跌幅",
        "f4": "涨跌额",
        "f8": "换手率",
        "f12": "板块代码",
        "f14": "板块名称",
        "f20": "总市值",
        "f104": "上涨家数",
        "f105": "下跌家数",
        "f128": "领涨股票",
        "f136": "领涨股票-涨跌幅",
    }

    # 选择需要的列并重命名
    selected_columns = list(columns_map.keys())
    available_columns = [col for col in selected_columns if col in temp_df.columns]
    temp_df = temp_df[available_columns]
    temp_df.rename(columns=columns_map, inplace=True)

    # 重置索引并添加排名列
    temp_df.reset_index(drop=True, inplace=True)
    temp_df.insert(0, "排名", range(1, len(temp_df) + 1))

    # 调整列顺序，与原函数保持一致
    final_columns = [
        "排名",
        "板块名称",
        "板块代码",
        "最新价",
        "涨跌额",
        "涨跌幅",
        "总市值",
        "换手率",
        "上涨家数",
        "下跌家数",
        "领涨股票",
        "领涨股票-涨跌幅",
    ]

    # 只保留存在的列
    final_columns = [col for col in final_columns if col in temp_df.columns]
    temp_df = temp_df[final_columns]

    return temp_df


async def stock_board_concept_name_em_async() -> pd.DataFrame:
    """
    异步获取东方财富网-行情中心-沪深京板块-概念板块-名称
    https://quote.eastmoney.com/center/boardlist.html#concept_board
    :return: 概念板块-名称
    :rtype: pandas.DataFrame
    """
    url = "https://79.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",  # 按涨跌幅排序，1为降序
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",  # 按涨跌幅排序
        "fs": "m:90 t:3 f:!50",
        "fields": "f2,f3,f4,f8,f12,f14,f15,f16,f17,f18,f20,f21,f24,f25,f22,f33,f11,f62,f128,f124,f107,f104,f105,f136",
    }

    results = await fetch_all_pages_async(url, params)
    return process_concept_board_data(results)


def stock_board_concept_name_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-沪深京板块-概念板块-名称 (同步接口)
    https://quote.eastmoney.com/center/boardlist.html#concept_board
    :return: 概念板块-名称
    :rtype: pandas.DataFrame
    """
    import nest_asyncio

    nest_asyncio.apply()
    return asyncio.run(stock_board_concept_name_em_async())


if __name__ == "__main__":
    # 测试同步接口
    stock_board_concept_name_em_df = stock_board_concept_name_em()
    print(stock_board_concept_name_em_df)
