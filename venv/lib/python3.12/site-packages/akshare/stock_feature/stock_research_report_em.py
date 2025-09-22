#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/2/28 13:00
Desc: 东方财富网-数据中心-研究报告-个股研报
https://data.eastmoney.com/report/stock.jshtml
"""

import datetime
import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_research_report_em(symbol: str = "000001") -> pd.DataFrame:
    """
    东方财富网-数据中心-研究报告-个股研报
    https://data.eastmoney.com/report/stock.jshtml
    :return: 个股研报
    :rtype: pandas.DataFrame
    """
    url = "https://reportapi.eastmoney.com/report/list"
    params = {
        "industryCode": "*",
        "pageSize": "5000",
        "industry": "*",
        "rating": "*",
        "ratingChange": "*",
        "beginTime": "2000-01-01",
        "endTime": f"{datetime.datetime.now().year + 1}-01-01",
        "pageNo": "1",
        "fields": "",
        "qType": "0",
        "orgCode": "",
        "code": symbol,
        "rcode": "",
        "p": "1",
        "pageNum": "1",
        "pageNumber": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["TotalPage"]
    current_year = data_json["currentYear"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pageNo": page,
                "p": page,
                "pageNum": page,
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        big_df = pd.concat(objs=[big_df, temp_df], axis=0, ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    predict_this_year_eps_title = f"{current_year}-盈利预测-收益"
    predict_this_year_pe_title = f"{current_year}-盈利预测-市盈率"
    predict_next_year_eps_title = f"{current_year + 1}-盈利预测-收益"
    predict_next_year_pe_title = f"{current_year + 1}-盈利预测-市盈率"
    predict_next_two_year_eps_title = f"{current_year + 2}-盈利预测-收益"
    predict_next_two_year_pe_title = f"{current_year + 2}-盈利预测-市盈率"
    big_df["pdfUrl"] = big_df["infoCode"].apply(
        lambda x: f"https://pdf.dfcfw.com/pdf/H3_{x}_1.pdf"
    )
    big_df.rename(
        columns={
            "index": "序号",
            "title": "报告名称",
            "stockName": "股票简称",
            "stockCode": "股票代码",
            "orgCode": "-",
            "orgName": "-",
            "orgSName": "机构",
            "publishDate": "日期",
            "infoCode": "-",
            "column": "-",
            "predictNextTwoYearEps": predict_next_two_year_eps_title,
            "predictNextTwoYearPe": predict_next_two_year_pe_title,
            "predictNextYearEps": predict_next_year_eps_title,
            "predictNextYearPe": predict_next_year_pe_title,
            "predictThisYearEps": predict_this_year_eps_title,
            "predictThisYearPe": predict_this_year_pe_title,
            "predictLastYearEps": "-",
            "predictLastYearPe": "-",
            "actualLastTwoYearEps": "-",
            "actualLastYearEps": "-",
            "industryCode": "-",
            "industryName": "-",
            "emIndustryCode": "-",
            "indvInduCode": "-",
            "indvInduName": "行业",
            "emRatingCode": "-",
            "emRatingValue": "-",
            "emRatingName": "东财评级",
            "lastEmRatingCode": "-",
            "lastEmRatingValue": "-",
            "lastEmRatingName": "-",
            "ratingChange": "-",
            "reportType": "-",
            "author": "-",
            "indvIsNew": "-",
            "researcher": "-",
            "newListingDate": "-",
            "newPurchaseDate": "-",
            "newIssuePrice": "-",
            "newPeIssueA": "-",
            "indvAimPriceT": "-",
            "indvAimPriceL": "-",
            "attachType": "-",
            "attachSize": "-",
            "attachPages": "-",
            "encodeUrl": "-",
            "sRatingName": "-",
            "sRatingCode": "-",
            "market": "-",
            "authorID": "-",
            "count": "近一月个股研报数",
            "orgType": "-",
            "pdfUrl": "报告PDF链接",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "报告名称",
            "东财评级",
            "机构",
            "近一月个股研报数",
            predict_this_year_eps_title,
            predict_this_year_pe_title,
            predict_next_year_eps_title,
            predict_next_year_pe_title,
            predict_next_two_year_eps_title,
            predict_next_two_year_pe_title,
            "行业",
            "日期",
            "报告PDF链接",
        ]
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["近一月个股研报数"] = pd.to_numeric(
        big_df["近一月个股研报数"], errors="coerce"
    )
    big_df[predict_this_year_eps_title] = pd.to_numeric(
        big_df[predict_this_year_eps_title], errors="coerce"
    )
    big_df[predict_this_year_pe_title] = pd.to_numeric(
        big_df[predict_this_year_pe_title], errors="coerce"
    )
    big_df[predict_next_year_eps_title] = pd.to_numeric(
        big_df[predict_next_year_eps_title], errors="coerce"
    )
    big_df[predict_next_year_pe_title] = pd.to_numeric(
        big_df[predict_next_year_pe_title], errors="coerce"
    )
    big_df[predict_next_two_year_eps_title] = pd.to_numeric(
        big_df[predict_next_two_year_eps_title], errors="coerce"
    )
    big_df[predict_next_two_year_pe_title] = pd.to_numeric(
        big_df[predict_next_two_year_pe_title], errors="coerce"
    )
    return big_df


if __name__ == "__main__":
    stock_research_report_em_df = stock_research_report_em(symbol="000001")
    print(stock_research_report_em_df)
