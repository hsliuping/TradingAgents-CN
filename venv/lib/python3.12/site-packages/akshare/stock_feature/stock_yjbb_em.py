#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/20 18:00
Desc: 东方财富-数据中心-年报季报
东方财富-数据中心-年报季报-业绩快报-业绩报表
https://data.eastmoney.com/bbsj/202003/yjbb.html
"""

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_yjbb_em(date: str = "20200331") -> pd.DataFrame:
    """
    东方财富-数据中心-年报季报-业绩快报-业绩报表
    https://data.eastmoney.com/bbsj/202003/yjbb.html
    :param date: "20200331", "20200630", "20200930", "20201231"; 从 20100331 开始
    :type date: str
    :return: 业绩报表
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.simplefilter(action="ignore", category=FutureWarning)  # 忽略所有
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "UPDATE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_LICO_FN_CPD",
        "columns": "ALL",
        "filter": f"(REPORTDATE='{'-'.join([date[:4], date[4:6], date[6:]])}')",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    big_list = []
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_list.append(temp_df)
    big_df = pd.concat(big_list, ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = range(1, len(big_df) + 1)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "_",
        "_",
        "_",
        "_",
        "最新公告日期",
        "_",
        "每股收益",
        "_",
        "营业总收入-营业总收入",
        "净利润-净利润",
        "净资产收益率",
        "营业总收入-同比增长",
        "净利润-同比增长",
        "每股净资产",
        "每股经营现金流量",
        "销售毛利率",
        "营业总收入-季度环比增长",
        "净利润-季度环比增长",
        "_",
        "_",
        "所处行业",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
    ]
    big_df = big_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "每股收益",
            "营业总收入-营业总收入",
            "营业总收入-同比增长",
            "营业总收入-季度环比增长",
            "净利润-净利润",
            "净利润-同比增长",
            "净利润-季度环比增长",
            "每股净资产",
            "净资产收益率",
            "每股经营现金流量",
            "销售毛利率",
            "所处行业",
            "最新公告日期",
        ]
    ]
    big_df["每股收益"] = pd.to_numeric(big_df["每股收益"], errors="coerce")
    big_df["营业总收入-营业总收入"] = pd.to_numeric(
        big_df["营业总收入-营业总收入"], errors="coerce"
    )
    big_df["营业总收入-同比增长"] = pd.to_numeric(
        big_df["营业总收入-同比增长"], errors="coerce"
    )
    big_df["营业总收入-季度环比增长"] = pd.to_numeric(
        big_df["营业总收入-季度环比增长"], errors="coerce"
    )
    big_df["净利润-净利润"] = pd.to_numeric(big_df["净利润-净利润"], errors="coerce")
    big_df["净利润-同比增长"] = pd.to_numeric(
        big_df["净利润-同比增长"], errors="coerce"
    )
    big_df["净利润-季度环比增长"] = pd.to_numeric(
        big_df["净利润-季度环比增长"], errors="coerce"
    )
    big_df["每股净资产"] = pd.to_numeric(big_df["每股净资产"], errors="coerce")
    big_df["净资产收益率"] = pd.to_numeric(big_df["净资产收益率"], errors="coerce")
    big_df["每股经营现金流量"] = pd.to_numeric(
        big_df["每股经营现金流量"], errors="coerce"
    )
    big_df["销售毛利率"] = pd.to_numeric(big_df["销售毛利率"], errors="coerce")
    big_df["最新公告日期"] = pd.to_datetime(
        big_df["最新公告日期"], errors="coerce"
    ).dt.date
    return big_df


if __name__ == "__main__":
    stock_yjbb_em_df = stock_yjbb_em(date="20220331")
    print(stock_yjbb_em_df)
