#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/2/28 17:00
Desc: 中国金融期货交易所-数据-交易参数
http://www.cffex.com.cn/jycs/
"""

import xml.etree.ElementTree as ET

import pandas as pd
import requests


def futures_contract_info_cffex(date: str = "20240228") -> pd.DataFrame:
    """
    中国金融期货交易所-数据-交易参数
    http://www.gfex.com.cn/gfex/hyxx/ywcs.shtml
    :return: 交易参数汇总查询
    :rtype: pandas.DataFrame
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    }
    url = f"http://www.cffex.com.cn/sj/jycs/{date[:6]}/{date[6:]}/index.xml"
    r = requests.get(url, headers=headers)
    xml_data = r.text
    # 解析 XML
    tree = ET.ElementTree(ET.fromstring(xml_data))
    root = tree.getroot()
    # 获取所有的记录
    records = root.findall(".//INDEX")
    # 解析数据并填充到列表中
    data = []
    for record in records:
        # 对于每个记录，创建一个字典
        row_data = {}
        for field in record:
            row_data[field.tag] = field.text
        # 将字典添加到数据列表中
        data.append(row_data)

    temp_df = pd.DataFrame(data)
    temp_df.rename(
        columns={
            "TRADING_DAY": "查询交易日",
            "PRODUCT_ID": "品种",
            "INSTRUMENT_ID": "合约代码",
            "INSTRUMENT_MONTH": "合约月份",
            "BASIS_PRICE": "挂盘基准价",
            "OPEN_DATE": "上市日",
            "END_TRADING_DAY": "最后交易日",
            "UPPER_VALUE": "涨停板幅度",
            "LOWER_VALUE": "跌停板幅度",
            "UPPERLIMITPRICE": "涨停板价位",
            "LOWERLIMITPRICE": "跌停板价位",
            "LONG_LIMIT": "持仓限额",
        },
        inplace=True,
    )
    temp_df["挂盘基准价"] = pd.to_numeric(temp_df["挂盘基准价"], errors="coerce")
    temp_df["涨停板价位"] = pd.to_numeric(temp_df["涨停板价位"], errors="coerce")
    temp_df["跌停板价位"] = pd.to_numeric(temp_df["跌停板价位"], errors="coerce")
    temp_df["持仓限额"] = pd.to_numeric(temp_df["持仓限额"], errors="coerce")

    temp_df["查询交易日"] = pd.to_datetime(
        temp_df["查询交易日"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df["上市日"] = pd.to_datetime(
        temp_df["上市日"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df["最后交易日"] = pd.to_datetime(
        temp_df["最后交易日"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df["查询交易日"] = pd.to_datetime(
        temp_df["查询交易日"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df = temp_df[
        [
            "合约代码",
            "合约月份",
            "挂盘基准价",
            "上市日",
            "最后交易日",
            "涨停板幅度",
            "跌停板幅度",
            "涨停板价位",
            "跌停板价位",
            "持仓限额",
            "品种",
            "查询交易日",
        ]
    ]
    temp_df.sort_values(["合约代码"], ascending=False, ignore_index=True, inplace=True)
    return temp_df


if __name__ == "__main__":
    futures_contract_info_cffex_df = futures_contract_info_cffex(date="20240228")
    print(futures_contract_info_cffex_df)
