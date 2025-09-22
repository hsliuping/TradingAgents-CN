#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/16 12:00
Desc: 东方财富网-行情首页-沪深京 A 股
https://quote.eastmoney.com/
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


def process_data(page_results: List[Dict]) -> pd.DataFrame:
    """处理获取到的数据，转换为DataFrame"""
    all_data = []

    # 保存每个页面的结果和页码
    page_number = 1
    items_per_page = 100  # 假设每页100条

    for result in page_results:
        if result.get("rc") == 0 and result.get("data") and result["data"].get("diff"):
            page_data = result["data"]["diff"]
            for item in page_data:
                item["page_number"] = page_number
                item["page_index"] = page_data.index(item)
            all_data.extend(page_data)
            page_number += 1
    if not all_data:
        return pd.DataFrame()
    df = pd.DataFrame(all_data)
    df["序号"] = df.apply(
        lambda row: (row["page_number"] - 1) * items_per_page + row["page_index"] + 1,
        axis=1,
    )
    df.drop(columns=["page_number", "page_index"], inplace=True, errors="ignore")
    column_map = {
        "f1": "原序号",
        "f2": "最新价",
        "f3": "涨跌幅",
        "f4": "涨跌额",
        "f5": "成交量",
        "f6": "成交额",
        "f7": "振幅",
        "f8": "换手率",
        "f9": "市盈率-动态",
        "f10": "量比",
        "f11": "5分钟涨跌",
        "f12": "代码",
        "f13": "_",
        "f14": "名称",
        "f15": "最高",
        "f16": "最低",
        "f17": "今开",
        "f18": "昨收",
        "f20": "总市值",
        "f21": "流通市值",
        "f22": "涨速",
        "f23": "市净率",
        "f24": "60日涨跌幅",
        "f25": "年初至今涨跌幅",
        "f62": "-",
        "f115": "-",
        "f128": "-",
        "f136": "-",
        "f152": "-",
    }

    df.rename(columns=column_map, inplace=True)
    desired_columns = [
        "序号",
        "代码",
        "名称",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "成交量",
        "成交额",
        "振幅",
        "最高",
        "最低",
        "今开",
        "昨收",
        "量比",
        "换手率",
        "市盈率-动态",
        "市净率",
        "总市值",
        "流通市值",
        "涨速",
        "5分钟涨跌",
        "60日涨跌幅",
        "年初至今涨跌幅",
    ]
    available_columns = [col for col in desired_columns if col in df.columns]
    df = df[available_columns]
    numeric_columns = [
        "最新价",
        "涨跌幅",
        "涨跌额",
        "成交量",
        "成交额",
        "振幅",
        "最高",
        "最低",
        "今开",
        "昨收",
        "量比",
        "换手率",
        "市盈率-动态",
        "市净率",
        "总市值",
        "流通市值",
        "涨速",
        "5分钟涨跌",
        "60日涨跌幅",
        "年初至今涨跌幅",
    ]
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_values(by="涨跌幅", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["序号"] = df.index + 1
    return df


async def stock_zh_a_spot_em_async() -> pd.DataFrame:
    """
    异步获取东方财富网-沪深京 A 股-实时行情
    https://quote.eastmoney.com/center/gridlist.html#hs_a_board
    :return: 实时行情
    :rtype: pandas.DataFrame
    """
    url = "https://82.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,"
        "f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152",
    }
    results = await fetch_all_pages_async(url, params)
    return process_data(results)


def stock_zh_a_spot_em() -> pd.DataFrame:
    """
    东方财富网-沪深京 A 股-实时行情 (同步接口)
    https://quote.eastmoney.com/center/gridlist.html#hs_a_board
    :return: 实时行情
    :rtype: pandas.DataFrame
    """
    import nest_asyncio

    nest_asyncio.apply()
    return asyncio.run(stock_zh_a_spot_em_async())


if __name__ == "__main__":
    stock_zh_a_spot_em_df = stock_zh_a_spot_em()
    print(stock_zh_a_spot_em_df)
