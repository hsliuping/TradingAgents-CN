#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/4 18:10
Desc: 东方财富-数据中心-年报季报
东方财富-数据中心-年报季报-业绩预告
https://data.eastmoney.com/bbsj/202003/yjyg.html
东方财富-数据中心-年报季报-预约披露时间
https://data.eastmoney.com/bbsj/202003/yysj.html
"""

import pandas as pd
import requests
from tqdm import tqdm


def stock_yjkb_em(date: str = "20211231") -> pd.DataFrame:
    """
    东方财富-数据中心-年报季报-业绩快报
    https://data.eastmoney.com/bbsj/202003/yjkb.html
    :param date: 财报发布日期; choice of {"20200331", "20200630", "20200930", "20201231", ...}; 从 20100331 开始
    :type date: str
    :return: 业绩快报
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    params = {
        "sortColumns": "UPDATE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_FCI_PERFORMANCEE",
        "columns": "ALL",
        "filter": f"""(SECURITY_TYPE_CODE in ("058001001","058001008"))(TRADE_MARKET_CODE!="069001017")
        (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    total_page = data_json["result"]["pages"]
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = range(1, len(big_df) + 1)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "市场板块",
        "_",
        "证券类型",
        "_",
        "公告日期",
        "_",
        "每股收益",
        "营业收入-营业收入",
        "营业收入-去年同期",
        "净利润-净利润",
        "净利润-去年同期",
        "每股净资产",
        "净资产收益率",
        "营业收入-同比增长",
        "净利润-同比增长",
        "营业收入-季度环比增长",
        "净利润-季度环比增长",
        "所处行业",
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
            "营业收入-营业收入",
            "营业收入-去年同期",
            "营业收入-同比增长",
            "营业收入-季度环比增长",
            "净利润-净利润",
            "净利润-去年同期",
            "净利润-同比增长",
            "净利润-季度环比增长",
            "每股净资产",
            "净资产收益率",
            "所处行业",
            "公告日期",
        ]
    ]
    big_df["每股收益"] = pd.to_numeric(big_df["每股收益"], errors="coerce")
    big_df["营业收入-营业收入"] = pd.to_numeric(
        big_df["营业收入-营业收入"], errors="coerce"
    )
    big_df["营业收入-去年同期"] = pd.to_numeric(
        big_df["营业收入-去年同期"], errors="coerce"
    )
    big_df["营业收入-同比增长"] = pd.to_numeric(
        big_df["营业收入-同比增长"], errors="coerce"
    )
    big_df["营业收入-季度环比增长"] = pd.to_numeric(
        big_df["营业收入-季度环比增长"], errors="coerce"
    )
    big_df["净利润-净利润"] = pd.to_numeric(big_df["净利润-净利润"], errors="coerce")
    big_df["净利润-去年同期"] = pd.to_numeric(
        big_df["净利润-去年同期"], errors="coerce"
    )
    big_df["净利润-同比增长"] = pd.to_numeric(
        big_df["净利润-同比增长"], errors="coerce"
    )
    big_df["净利润-季度环比增长"] = pd.to_numeric(
        big_df["净利润-季度环比增长"], errors="coerce"
    )
    big_df["每股净资产"] = pd.to_numeric(big_df["每股净资产"], errors="coerce")
    big_df["净资产收益率"] = pd.to_numeric(big_df["净资产收益率"], errors="coerce")
    big_df["净资产收益率"] = pd.to_numeric(big_df["净资产收益率"], errors="coerce")
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"]).dt.date
    return big_df


def stock_yjyg_em(date: str = "20200331") -> pd.DataFrame:
    """
    东方财富-数据中心-年报季报-业绩预告
    https://data.eastmoney.com/bbsj/202003/yjyg.html
    :param date: 财报发布日期; choice of {"20200331", "20200630", "20200930", "20201231", ...}; 从 20081231 开始
    :type date: str
    :return: 业绩预告
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_PUBLIC_OP_NEWPREDICT",
        "columns": "ALL",
        "filter": f" (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    total_page = data_json["result"]["pages"]
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = range(1, len(big_df) + 1)
    big_df.columns = [
        "序号",
        "_",
        "股票代码",
        "股票简称",
        "_",
        "公告日期",
        "报告日期",
        "_",
        "预测指标",
        "_",
        "_",
        "_",
        "_",
        "业绩变动",
        "业绩变动原因",
        "预告类型",
        "上年同期值",
        "_",
        "_",
        "_",
        "_",
        "业绩变动幅度",
        "预测数值",
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
            "预测指标",
            "业绩变动",
            "预测数值",
            "业绩变动幅度",
            "业绩变动原因",
            "预告类型",
            "上年同期值",
            "公告日期",
        ]
    ]
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date
    big_df["业绩变动幅度"] = pd.to_numeric(big_df["业绩变动幅度"], errors="coerce")
    big_df["预测数值"] = pd.to_numeric(big_df["预测数值"], errors="coerce")
    big_df["上年同期值"] = pd.to_numeric(big_df["上年同期值"], errors="coerce")
    return big_df


def stock_yysj_em(symbol: str = "沪深A股", date: str = "20200331") -> pd.DataFrame:
    """
    东方财富-数据中心-年报季报-预约披露时间
    https://data.eastmoney.com/bbsj/202003/yysj.html
    :param symbol: choice of {'沪深A股', '沪市A股', '科创板', '深市A股', '创业板', '京市A股', 'ST板'}
    :type symbol: str
    :param date: "20190331", "20190630", "20190930", "20191231"; 从 20081231 开始
    :type date: str
    :return: 指定时间的上市公司预约披露时间数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "FIRST_APPOINT_DATE,SECURITY_CODE",
        "sortTypes": "1,1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_PUBLIC_BS_APPOIN",
        "columns": "ALL",
        "filter": f"""(SECURITY_TYPE_CODE in ("058001001","058001008"))(TRADE_MARKET_CODE!="069001017")
        (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')""",
    }
    if symbol == "沪市A股":
        params.update(
            {
                "filter": f"""(SECURITY_TYPE_CODE in ("058001001","058001008"))
                (TRADE_MARKET_CODE in ("069001001001","069001001003","069001001006"))
                (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')"""
            }
        )
    elif symbol == "科创板":
        params.update(
            {
                "filter": f"""(SECURITY_TYPE_CODE in ("058001001","058001008"))(TRADE_MARKET_CODE="069001001006")
                (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')"""
            }
        )
    elif symbol == "深市A股":
        params.update(
            {
                "filter": f"""(SECURITY_TYPE_CODE="058001001")(TRADE_MARKET_CODE in
                ("069001002001","069001002002","069001002003","069001002005"))
                (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')"""
            }
        )
    elif symbol == "创业板":
        params.update(
            {
                "filter": f"""(SECURITY_TYPE_CODE="058001001")(TRADE_MARKET_CODE="069001002002")
                (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')"""
            }
        )
    elif symbol == "京市A股":
        params.update(
            {
                "filter": f"""(TRADE_MARKET_CODE="069001017")
                (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')"""
            }
        )
    elif symbol == "ST板":
        params.update(
            {
                "filter": f"""(TRADE_MARKET_CODE in("069001001003","069001002005"))
                (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')"""
            }
        )
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = range(1, len(big_df) + 1)
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "_",
        "_",
        "首次预约时间",
        "一次变更日期",
        "二次变更日期",
        "三次变更日期",
        "实际披露时间",
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
            "首次预约时间",
            "一次变更日期",
            "二次变更日期",
            "三次变更日期",
            "实际披露时间",
        ]
    ]
    big_df["首次预约时间"] = pd.to_datetime(
        big_df["首次预约时间"], errors="coerce"
    ).dt.date
    big_df["一次变更日期"] = pd.to_datetime(
        big_df["一次变更日期"], errors="coerce"
    ).dt.date
    big_df["二次变更日期"] = pd.to_datetime(
        big_df["二次变更日期"], errors="coerce"
    ).dt.date
    big_df["三次变更日期"] = pd.to_datetime(
        big_df["三次变更日期"], errors="coerce"
    ).dt.date
    big_df["实际披露时间"] = pd.to_datetime(
        big_df["实际披露时间"], errors="coerce"
    ).dt.date
    return big_df


if __name__ == "__main__":
    stock_yjkb_em_df = stock_yjkb_em(date="20200331")
    print(stock_yjkb_em_df)

    stock_yjyg_em_df = stock_yjyg_em(date="20250331")
    print(stock_yjyg_em_df)

    stock_yysj_em_df = stock_yysj_em(symbol="沪深A股", date="20211231")
    print(stock_yysj_em_df)
