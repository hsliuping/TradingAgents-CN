#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/9/15 15:30
Desc: 东方财富网-数据中心-特色数据-商誉
东方财富网-数据中心-特色数据-商誉-A股商誉市场概况: https://data.eastmoney.com/sy/scgk.html
东方财富网-数据中心-特色数据-商誉-商誉减值预期明细: https://data.eastmoney.com/sy/yqlist.html
东方财富网-数据中心-特色数据-商誉-个股商誉减值明细: https://data.eastmoney.com/sy/jzlist.html
东方财富网-数据中心-特色数据-商誉-个股商誉明细: https://data.eastmoney.com/sy/list.html
东方财富网-数据中心-特色数据-商誉-行业商誉: https://data.eastmoney.com/sy/hylist.html
"""

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_sy_profile_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-商誉-A股商誉市场概况
    https://data.eastmoney.com/sy/scgk.html
    :return: A股商誉市场概况
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_GOODWILL_MARKETSTATISTICS",
        "token": "894050c76af8597a853f5b408b759f5d",
        "columns": "ALL",
        "filter": """((GOODWILL_STATE="1")( | IMPAIRMENT_STATE="1"))(TRADE_BOARD="all")""",
    }

    r = requests.get(url, params=params)
    data_json = r.json()
    data_df = pd.DataFrame(data_json["result"]["data"])
    data_df.columns = [
        "_",
        "报告期",
        "商誉",
        "商誉减值",
        "净资产",
        "商誉占净资产比例",
        "商誉减值占净资产比例",
        "净利润规模",
        "商誉减值占净利润比例",
        "_",
        "_",
    ]
    data_df = data_df[
        [
            "报告期",
            "商誉",
            "商誉减值",
            "净资产",
            "商誉占净资产比例",
            "商誉减值占净资产比例",
            "净利润规模",
            "商誉减值占净利润比例",
        ]
    ]
    data_df["报告期"] = pd.to_datetime(data_df["报告期"], errors="coerce").dt.date
    data_df["商誉"] = pd.to_numeric(data_df["商誉"], errors="coerce")
    data_df["商誉减值"] = pd.to_numeric(data_df["商誉减值"], errors="coerce")
    data_df["净资产"] = pd.to_numeric(data_df["净资产"], errors="coerce")
    data_df["商誉占净资产比例"] = pd.to_numeric(
        data_df["商誉占净资产比例"], errors="coerce"
    )
    data_df["商誉减值占净资产比例"] = pd.to_numeric(
        data_df["商誉减值占净资产比例"], errors="coerce"
    )
    data_df["净利润规模"] = pd.to_numeric(data_df["净利润规模"], errors="coerce")
    data_df["商誉减值占净利润比例"] = pd.to_numeric(
        data_df["商誉减值占净利润比例"], errors="coerce"
    )
    data_df.sort_values(["报告期"], inplace=True, ignore_index=True)
    return data_df


def stock_sy_yq_em(date: str = "20240630") -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-商誉-商誉减值预期明细
    https://data.eastmoney.com/sy/yqlist.html
    :param date: 参考网站指定的数据日期
    :type date: str
    :return: 商誉减值预期明细
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "columns": "ALL",
        "token": "894050c76af8597a853f5b408b759f5d",
        "reportName": "RPT_GOODWILL_STOCKPREDICT",
        "filter": f"""(REPORT_DATE='{"-".join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    total_page = int(data_json["result"]["pages"])
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    big_df.rename(
        columns={
            "index": "序号",
            "SECUCODE": "-",
            "SECURITY_CODE": "股票代码",
            "ORG_CODE": "-",
            "SECURITY_NAME_ABBR": "股票简称",
            "TRADE_MARKET": "交易市场",
            "INDUSTRY_NAME": "-",
            "INDUSTRY_CODE": "-",
            "NOTICE_DATE": "公告日期",
            "REPORT_DATE": "数据日期",
            "PE_REPORT_DATE": "-",
            "PREDICT_NETPROFIT_LOWER": "预计净利润-下限",
            "PREDICT_NETPROFIT_UPPER": "预计净利润-上限",
            "PERFORM_CHANGE_UPPER": "业绩变动幅度-上限",
            "PERFORM_CHANGE_LOWER": "业绩变动幅度-下限",
            "PERFORM_CHANGE": "-",
            "PERFORM_CHANGE_EXPLAIN": "业绩变动原因",
            "PREDICT_TYPE": "-",
            "PREDICT_INDICATOR_CODE": "-",
            "PREDICT_PERIOD": "-",
            "PE_SAMEREPORT_NETPROFIT": "上年度同期净利润",
            "NETPROFIT": "-",
            "PE_GOODWILL": "上年商誉",
            "NEWEST_REPORT_DATE": "最新商誉报告期",
            "NEWEST_GOODWILL": "最新一期商誉",
            "PE_SAMEREPORT_DATE": "-",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "业绩变动原因",
            "最新商誉报告期",
            "最新一期商誉",
            "上年商誉",
            "预计净利润-下限",
            "预计净利润-上限",
            "业绩变动幅度-下限",
            "业绩变动幅度-上限",
            "上年度同期净利润",
            "公告日期",
            "交易市场",
        ]
    ]
    big_df["交易市场"] = big_df["交易市场"].map(
        {"shzb": "沪市主板", "kcb": "科创板", "szzb": "深市主板", "cyb": "创业板"}
    )
    big_df["最新商誉报告期"] = pd.to_datetime(
        big_df["最新商誉报告期"], errors="coerce"
    ).dt.date
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date
    big_df["最新一期商誉"] = pd.to_numeric(big_df["最新一期商誉"], errors="coerce")
    big_df["上年商誉"] = pd.to_numeric(big_df["上年商誉"], errors="coerce")
    big_df["预计净利润-下限"] = pd.to_numeric(
        big_df["预计净利润-下限"], errors="coerce"
    )
    big_df["预计净利润-上限"] = pd.to_numeric(
        big_df["预计净利润-上限"], errors="coerce"
    )
    big_df["业绩变动幅度-下限"] = pd.to_numeric(
        big_df["业绩变动幅度-下限"], errors="coerce"
    )
    big_df["业绩变动幅度-上限"] = pd.to_numeric(
        big_df["业绩变动幅度-上限"], errors="coerce"
    )
    big_df["上年度同期净利润"] = pd.to_numeric(
        big_df["上年度同期净利润"], errors="coerce"
    )
    return big_df


def stock_sy_jz_em(date: str = "20240630") -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-商誉-个股商誉减值明细
    https://data.eastmoney.com/sy/jzlist.html
    :param date: 参考网站指定的数据日期
    :type date: str
    :return: 个股商誉减值明细
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "GOODWILL_CHANGE",
        "sortTypes": "-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "columns": "ALL",
        "token": "894050c76af8597a853f5b408b759f5d",
        "reportName": "RPT_GOODWILL_STOCKDETAILS",
        "filter": f"""(REPORT_DATE='{"-".join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    total_page = int(data_json["result"]["pages"])
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    big_df.rename(
        columns={
            "index": "序号",
            "SECUCODE": "-",
            "SECURITY_CODE": "股票代码",
            "SECURITY_NAME_ABBR": "股票简称",
            "ORG_CODE": "-",
            "LISTING_DATE": "-",
            "LISTING_STATE": "-",
            "TRADE_BOARD": "交易市场",
            "GOODWILL": "商誉",
            "DATE_TYPE": "-",
            "REPORT_TYPE_CODE": "-",
            "DATA_ADJUST_TYPE": "-",
            "NOTICE_DATE": "公告日期",
            "REPORT_DATE": "数据日期",
            "GOODWILL_PRE": "-",
            "GOODWILL_CHANGE": "商誉减值",
            "SUMSHEQUITY": "-",
            "SUMSHEQUITY_RATIO": "商誉占净资产比例",
            "SE_CHANGE_RATIO": "商誉减值占净资产比例",
            "PARENTNETPROFIT": "净利润",
            "PNP_CHANGE_RATIO": "商誉减值占净利润比例",
            "PNP_YOY_RATIO": "-",
            "INDUSTRY_CFT": "-",
            "INDUSTRY_CFTCODE": "-",
            "IS_SHOW": "-",
            "MAXREPORTDATE": "-",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "商誉",
            "商誉减值",
            "商誉占净资产比例",
            "商誉减值占净资产比例",
            "净利润",
            "商誉减值占净利润比例",
            "公告日期",
            "交易市场",
        ]
    ]
    big_df["交易市场"] = big_df["交易市场"].map(
        {"shzb": "沪市主板", "kcb": "科创板", "szzb": "深市主板", "cyb": "创业板"}
    )
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date
    big_df["商誉"] = pd.to_numeric(big_df["商誉"], errors="coerce")
    big_df["商誉减值"] = pd.to_numeric(big_df["商誉减值"], errors="coerce")
    big_df["商誉占净资产比例"] = pd.to_numeric(
        big_df["商誉占净资产比例"], errors="coerce"
    )
    big_df["商誉减值占净资产比例"] = pd.to_numeric(
        big_df["商誉减值占净资产比例"], errors="coerce"
    )
    big_df["净利润"] = pd.to_numeric(big_df["净利润"], errors="coerce")
    big_df["商誉减值占净利润比例"] = pd.to_numeric(
        big_df["商誉减值占净利润比例"], errors="coerce"
    )
    big_df["商誉减值占净利润比例"] = pd.to_numeric(
        big_df["商誉减值占净利润比例"], errors="coerce"
    )
    return big_df


def stock_sy_em(date: str = "20231231") -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-商誉-个股商誉明细
    https://data.eastmoney.com/sy/list.html
    :param date: 参考网站指定的数据日期
    :type date: str
    :return: 个股商誉明细
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "columns": "ALL",
        "token": "894050c76af8597a853f5b408b759f5d",
        "reportName": "RPT_GOODWILL_STOCKDETAILS",
        "filter": f"""(REPORT_DATE='{"-".join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    total_page = int(data_json["result"]["pages"])
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    big_df.rename(
        columns={
            "index": "序号",
            "SECUCODE": "-",
            "SECURITY_CODE": "股票代码",
            "SECURITY_NAME_ABBR": "股票简称",
            "ORG_CODE": "-",
            "LISTING_DATE": "-",
            "LISTING_STATE": "-",
            "TRADE_BOARD": "交易市场",
            "GOODWILL": "商誉",
            "DATE_TYPE": "-",
            "REPORT_TYPE_CODE": "-",
            "DATA_ADJUST_TYPE": "-",
            "NOTICE_DATE": "公告日期",
            "REPORT_DATE": "数据日期",
            "GOODWILL_PRE": "上年商誉",
            "GOODWILL_CHANGE": "商誉减值",
            "SUMSHEQUITY": "-",
            "SUMSHEQUITY_RATIO": "商誉占净资产比例",
            "SE_CHANGE_RATIO": "商誉减值占净资产比例",
            "PARENTNETPROFIT": "净利润",
            "PNP_CHANGE_RATIO": "商誉减值占净利润比例",
            "PNP_YOY_RATIO": "净利润同比",
            "INDUSTRY_CFT": "-",
            "INDUSTRY_CFTCODE": "-",
            "IS_SHOW": "-",
            "MAXREPORTDATE": "-",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "商誉",
            "商誉占净资产比例",
            "净利润",
            "净利润同比",
            "上年商誉",
            "公告日期",
            "交易市场",
        ]
    ]
    big_df["交易市场"] = big_df["交易市场"].map(
        {"shzb": "沪市主板", "kcb": "科创板", "szzb": "深市主板", "cyb": "创业板"}
    )
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date
    big_df["商誉"] = pd.to_numeric(big_df["商誉"], errors="coerce")
    big_df["商誉占净资产比例"] = pd.to_numeric(
        big_df["商誉占净资产比例"], errors="coerce"
    )
    big_df["净利润"] = pd.to_numeric(big_df["净利润"], errors="coerce")
    big_df["净利润同比"] = pd.to_numeric(big_df["净利润同比"], errors="coerce")
    big_df["上年商誉"] = pd.to_numeric(big_df["上年商誉"], errors="coerce")
    return big_df


def stock_sy_hy_em(date: str = "20240930") -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-商誉-行业商誉
    https://data.eastmoney.com/sy/hylist.html
    :param date: 参考网站指定的数据日期
    :type date: str
    :return: 个股商誉明细
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "SUMSHEQUITY_RATIO",
        "sortTypes": "-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "columns": "ALL",
        "token": "894050c76af8597a853f5b408b759f5d",
        "reportName": "RPT_GOODWILL_INDUSTATISTICS",
        "filter": f"""(REPORT_DATE='{"-".join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    big_df = pd.DataFrame()
    total_page = int(data_json["result"]["pages"])
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True, drop=True)
    big_df.rename(
        columns={
            "REPORT_DATE": "数据日期",
            "INDUSTRY_NAME": "行业名称",
            "INDUSTRY_CODE": "-",
            "ORG_NUM": "公司家数",
            "GOODWILL": "商誉规模",
            "GOODWILL_CHANGE": "-",
            "SUMSHEQUITY": "净资产",
            "SUMSHEQUITY_RATIO": "商誉规模占净资产规模比例",
            "SE_CHANGE_RATIO": "-",
            "PARENTNETPROFIT": "净利润规模",
            "PNP_CHANGE_RATIO": "-",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "行业名称",
            "公司家数",
            "商誉规模",
            "净资产",
            "商誉规模占净资产规模比例",
            "净利润规模",
        ]
    ]
    big_df["公司家数"] = pd.to_numeric(big_df["公司家数"], errors="coerce")
    big_df["商誉规模"] = pd.to_numeric(big_df["商誉规模"], errors="coerce")
    big_df["净资产"] = pd.to_numeric(big_df["净资产"], errors="coerce")
    big_df["商誉规模占净资产规模比例"] = pd.to_numeric(
        big_df["商誉规模占净资产规模比例"], errors="coerce"
    )
    big_df["净利润规模"] = pd.to_numeric(big_df["净利润规模"], errors="coerce")
    return big_df


if __name__ == "__main__":
    stock_sy_profile_em_df = stock_sy_profile_em()
    print(stock_sy_profile_em_df)

    stock_sy_yq_em_df = stock_sy_yq_em(date="20240630")
    print(stock_sy_yq_em_df)

    stock_sy_jz_em_df = stock_sy_jz_em(date="20240630")
    print(stock_sy_jz_em_df)

    stock_sy_em_df = stock_sy_em(date="20240630")
    print(stock_sy_em_df)

    stock_sy_hy_em_df = stock_sy_hy_em(date="20240930")
    print(stock_sy_hy_em_df)
