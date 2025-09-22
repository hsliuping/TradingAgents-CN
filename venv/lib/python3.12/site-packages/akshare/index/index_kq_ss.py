#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/6/13 22:05
Desc: 柯桥时尚指数
http://ss.kqindex.cn:9559/rinder_web_kqsszs/index/index_page.do
"""

import pandas as pd
import requests


def index_kq_fashion(symbol: str = "时尚创意指数") -> pd.DataFrame:
    """
    柯桥时尚指数
    http://ss.kqindex.cn:9559/rinder_web_kqsszs/index/index_page.do
    :param symbol: choice of {'柯桥时尚指数', '时尚创意指数', '时尚设计人才数', '新花型推出数', '创意产品成交数', '创意企业数量', '时尚活跃度指数', '电商运行数', '时尚平台拓展数', '新产品销售额占比', '企业合作占比', '品牌传播费用', '时尚推广度指数', '国际交流合作次数', '企业参展次数', '外商驻点数量变化', '时尚评价指数'}
    :type symbol: str
    :return: 柯桥时尚指数及其子项数据
    :rtype: pandas.DataFrame
    """
    url = "http://api.idx365.com/index/project/34/data"
    symbol_map = {
        "柯桥时尚指数": "root",
        "时尚创意指数": "01",
        "时尚设计人才数": "0101",
        "新花型推出数": "0102",
        "创意产品成交数": "0103",
        "创意企业数量": "0104",
        "时尚活跃度指数": "02",
        "电商运行数": "0201",
        "时尚平台拓展数": "0201",
        "新产品销售额占比": "0201",
        "企业合作占比": "0201",
        "品牌传播费用": "0201",
        "时尚推广度指数": "03",
        "国际交流合作次数": "0301",
        "企业参展次数": "0302",
        "外商驻点数量变化": "0302",
        "时尚评价指数": "04",
    }
    params = {"structCode": symbol_map[symbol]}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.rename(
        columns={
            "id": "_",
            "indexValue": "指数",
            "lastValue": "_",
            "projId": "_",
            "publishTime": "日期",
            "sameValue": "_",
            "stageId": "_",
            "structCode": "_",
            "structName": "_",
            "version": "_",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "日期",
            "指数",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"]).dt.date
    temp_df.sort_values("日期", inplace=True)
    temp_df["涨跌值"] = temp_df["指数"].diff()
    temp_df["涨跌幅"] = temp_df["指数"].pct_change()
    temp_df.sort_values("日期", ascending=True, inplace=True, ignore_index=True)
    return temp_df


if __name__ == "__main__":
    for item in [
        "柯桥时尚指数",
        "时尚创意指数",
        "时尚设计人才数",
        "新花型推出数",
        "创意产品成交数",
        "创意企业数量",
        "时尚活跃度指数",
        "电商运行数",
        "时尚平台拓展数",
        "新产品销售额占比",
        "企业合作占比",
        "品牌传播费用",
        "时尚推广度指数",
        "国际交流合作次数",
        "企业参展次数",
        "外商驻点数量变化",
        "时尚评价指数",
    ]:
        index_kq_fashion_df = index_kq_fashion(symbol=item)
        print(item)
        print(index_kq_fashion_df)
