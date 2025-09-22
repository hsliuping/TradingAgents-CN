# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/6/13 13:00
Desc: 东方财富网-数据中心-公告大全-沪深 A 股公告
https://data.eastmoney.com/notices/hsa/5.html
"""

import math

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_notice_report(symbol: str = "全部", date: str = "20220511") -> pd.DataFrame:
    """
    东方财富网-数据中心-公告大全-沪深京 A 股公告
    https://data.eastmoney.com/notices/hsa/5.html
    :param symbol: 报告类型; choice of {"全部", "重大事项", "财务报告", "融资公告", "风险提示", "资产重组", "信息变更", "持股变动"}
    :type symbol: str
    :param date: 制定日期
    :type date: str
    :return: 沪深京 A 股公告
    :rtype: pandas.DataFrame
    """
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    report_map = {
        "全部": "0",
        "财务报告": "1",
        "融资公告": "2",
        "风险提示": "3",
        "信息变更": "4",
        "重大事项": "5",
        "资产重组": "6",
        "持股变动": "7",
    }
    params = {
        "sr": "-1",
        "page_size": "100",
        "page_index": "1",
        "ann_type": "A",
        "client_source": "web",
        "f_node": report_map[symbol],
        "s_node": "0",
        "begin_time": "-".join([date[:4], date[4:6], date[6:]]),
        "end_time": "-".join([date[:4], date[4:6], date[6:]]),
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = math.ceil(data_json["data"]["total_hits"] / 100)
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, int(total_page) + 1), leave=False):
        params.update(
            {
                "page_index": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["list"])
        temp_codes_df = pd.DataFrame(
            [item["codes"][0] for item in data_json["data"]["list"]]
        )
        try:
            temp_columns_df = pd.DataFrame(
                [item["columns"][0] for item in data_json["data"]["list"]]
            )
        except:  # noqa: E722
            continue
        del temp_df["codes"]
        del temp_df["columns"]
        temp_df = pd.concat(objs=[temp_df, temp_columns_df, temp_codes_df], axis=1)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.rename(
        columns={
            "art_code": "编码",
            "display_time": "-",
            "eiTime": "-",
            "notice_date": "公告日期",
            "title": "公告标题",
            "column_code": "-",
            "column_name": "公告类型",
            "ann_type": "-",
            "inner_code": "-",
            "market_code": "-",
            "short_name": "名称",
            "stock_code": "代码",
        },
        inplace=True,
    )
    url = "https://data.eastmoney.com/notices/detail/"
    big_df["网址"] = url + big_df["代码"] + "/" + big_df["编码"] + ".html"
    big_df = big_df[
        [
            "代码",
            "名称",
            "公告标题",
            "公告类型",
            "公告日期",
            "网址",
        ]
    ]
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date
    return big_df


if __name__ == "__main__":
    stock_notice_report_df = stock_notice_report(symbol="财务报告", date="20240612")
    print(stock_notice_report_df)

    item_list = [
        "全部",
        "财务报告",
        "融资公告",
        "风险提示",
        "信息变更",
        "重大事项",
        "资产重组",
        "持股变动",
    ]
    for temp_item in item_list:
        stock_notice_report_df = stock_notice_report(symbol=temp_item, date="20220511")
        print(stock_notice_report_df)
