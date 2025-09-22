#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/7/21 18:00
Desc: 科创板报告
https://data.eastmoney.com/notices/kcb.html
"""

import pandas as pd
import requests
from tqdm import tqdm


def _stock_zh_kcb_report_em_page() -> int:
    """
    科创板报告的页数
    https://data.eastmoney.com/notices/kcb.html
    :return: 科创板报告的页数
    :rtype: int
    """
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        "sr": "-1",
        "page_size": "100",
        "page_index": "1",
        "ann_type": "KCB",
        "client_source": "web",
        "f_node": "0",
        "s_node": "0",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    page_num = int(
        int(data_json["data"]["total_hits"]) / int(data_json["data"]["page_size"])
    )
    return page_num


def stock_zh_kcb_report_em(from_page: int = 1, to_page: int = 100) -> pd.DataFrame:
    """
    科创板报告内容
    https://data.eastmoney.com/notices/kcb.html
    :param from_page: 开始获取的页码
    :type from_page: int
    :param to_page: 结束获取的页码
    :type to_page: int
    :return: 科创板报告内容
    :rtype: pandas.DataFrame
    """
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    total_page = _stock_zh_kcb_report_em_page()
    big_df = pd.DataFrame()
    if to_page >= total_page:
        to_page = total_page
    for i in tqdm(range(from_page, to_page + 1), leave=False):
        params = {
            "sr": "-1",
            "page_size": "100",
            "page_index": i,
            "ann_type": "KCB",
            "client_source": "web",
            "f_node": "0",
            "s_node": "0",
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            [
                [item["codes"][0]["stock_code"] for item in data_json["data"]["list"]],
                [item["codes"][0]["short_name"] for item in data_json["data"]["list"]],
                [item["title"] for item in data_json["data"]["list"]],
                [
                    item["columns"][0]["column_name"]
                    for item in data_json["data"]["list"]
                ],
                [item["notice_date"] for item in data_json["data"]["list"]],
                [item["art_code"] for item in data_json["data"]["list"]],
            ]
        ).T
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.columns = [
        "代码",
        "名称",
        "公告标题",
        "公告类型",
        "公告日期",
        "公告代码",
    ]
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date
    return big_df


if __name__ == "__main__":
    stock_zh_kcb_report_em_df = stock_zh_kcb_report_em(from_page=1, to_page=100)
    print(stock_zh_kcb_report_em_df)
