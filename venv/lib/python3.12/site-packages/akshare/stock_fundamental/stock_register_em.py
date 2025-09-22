# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/6/15 20:20
Desc: 东方财富网-数据中心-新股数据-注册制审核
https://data.eastmoney.com/kcb/?type=nsb
"""

import pandas as pd
import requests

from akshare.utils.cons import headers
from akshare.utils.tqdm import get_tqdm


def stock_register_kcb() -> pd.DataFrame:
    """
    东方财富网-数据中心-新股数据-IPO审核信息-科创板
    https://data.eastmoney.com/xg/ipo/
    :return: 科创板注册制审核结果
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "UPDATE_DATE,ORG_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_IPO_INFOALLNEW",
        "columns": "SECURITY_CODE,STATE,REG_ADDRESS,INFO_CODE,CSRC_INDUSTRY,ACCEPT_DATE,DECLARE_ORG,"
        "PREDICT_LISTING_MARKET,LAW_FIRM,ACCOUNT_FIRM,ORG_CODE,UPDATE_DATE,RECOMMEND_ORG,IS_REGISTRATION",
        "source": "WEB",
        "client": "WEB",
        "filter": '(PREDICT_LISTING_MARKET="科创板")',
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.rename(
        columns={
            "index": "序号",
            "DECLARE_ORG": "企业名称",
            "STATE": "最新状态",
            "REG_ADDRESS": "注册地",
            "CSRC_INDUSTRY": "行业",
            "RECOMMEND_ORG": "保荐机构",
            "LAW_FIRM": "律师事务所",
            "ACCOUNT_FIRM": "会计师事务所",
            "UPDATE_DATE": "更新日期",
            "ACCEPT_DATE": "受理日期",
            "PREDICT_LISTING_MARKET": "拟上市地点",
            "INFO_CODE": "招股说明书",
        },
        inplace=True,
    )
    big_df["招股说明书"] = [
        f"https://pdf.dfcfw.com/pdf/H2_{item}_1.pdf" for item in big_df["招股说明书"]
    ]
    big_df = big_df[
        [
            "序号",
            "企业名称",
            "最新状态",
            "注册地",
            "行业",
            "保荐机构",
            "律师事务所",
            "会计师事务所",
            "更新日期",
            "受理日期",
            "拟上市地点",
            "招股说明书",
        ]
    ]
    big_df["更新日期"] = pd.to_datetime(big_df["更新日期"], errors="coerce").dt.date
    big_df["受理日期"] = pd.to_datetime(big_df["受理日期"], errors="coerce").dt.date
    return big_df


def stock_register_cyb() -> pd.DataFrame:
    """
    东方财富网-数据中心-新股数据-IPO审核信息-创业板
    https://data.eastmoney.com/xg/ipo/
    :return: 创业板注册制审核结果
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "UPDATE_DATE,ORG_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_IPO_INFOALLNEW",
        "columns": "SECURITY_CODE,STATE,REG_ADDRESS,INFO_CODE,CSRC_INDUSTRY,ACCEPT_DATE,DECLARE_ORG,"
        "PREDICT_LISTING_MARKET,LAW_FIRM,ACCOUNT_FIRM,ORG_CODE,UPDATE_DATE,RECOMMEND_ORG,IS_REGISTRATION",
        "source": "WEB",
        "client": "WEB",
        "filter": '(PREDICT_LISTING_MARKET="创业板")',
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.rename(
        columns={
            "index": "序号",
            "DECLARE_ORG": "企业名称",
            "STATE": "最新状态",
            "REG_ADDRESS": "注册地",
            "CSRC_INDUSTRY": "行业",
            "RECOMMEND_ORG": "保荐机构",
            "LAW_FIRM": "律师事务所",
            "ACCOUNT_FIRM": "会计师事务所",
            "UPDATE_DATE": "更新日期",
            "ACCEPT_DATE": "受理日期",
            "PREDICT_LISTING_MARKET": "拟上市地点",
            "INFO_CODE": "招股说明书",
        },
        inplace=True,
    )
    big_df["招股说明书"] = [
        f"https://pdf.dfcfw.com/pdf/H2_{item}_1.pdf" for item in big_df["招股说明书"]
    ]
    big_df = big_df[
        [
            "序号",
            "企业名称",
            "最新状态",
            "注册地",
            "行业",
            "保荐机构",
            "律师事务所",
            "会计师事务所",
            "更新日期",
            "受理日期",
            "拟上市地点",
            "招股说明书",
        ]
    ]
    big_df["更新日期"] = pd.to_datetime(big_df["更新日期"], errors="coerce").dt.date
    big_df["受理日期"] = pd.to_datetime(big_df["受理日期"], errors="coerce").dt.date
    return big_df


def stock_register_bj() -> pd.DataFrame:
    """
    东方财富网-数据中心-新股数据-IPO审核信息-北交所
    https://data.eastmoney.com/xg/ipo/
    :return: 北交所
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "UPDATE_DATE,ORG_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_IPO_INFOALLNEW",
        "columns": "SECURITY_CODE,STATE,REG_ADDRESS,INFO_CODE,CSRC_INDUSTRY,ACCEPT_DATE,DECLARE_ORG,"
        "PREDICT_LISTING_MARKET,LAW_FIRM,ACCOUNT_FIRM,ORG_CODE,UPDATE_DATE,RECOMMEND_ORG,IS_REGISTRATION",
        "source": "WEB",
        "client": "WEB",
        "filter": '(PREDICT_LISTING_MARKET="北交所")',
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.rename(
        columns={
            "index": "序号",
            "DECLARE_ORG": "企业名称",
            "STATE": "最新状态",
            "REG_ADDRESS": "注册地",
            "CSRC_INDUSTRY": "行业",
            "RECOMMEND_ORG": "保荐机构",
            "LAW_FIRM": "律师事务所",
            "ACCOUNT_FIRM": "会计师事务所",
            "UPDATE_DATE": "更新日期",
            "ACCEPT_DATE": "受理日期",
            "PREDICT_LISTING_MARKET": "拟上市地点",
            "INFO_CODE": "招股说明书",
        },
        inplace=True,
    )
    big_df["招股说明书"] = [
        f"https://pdf.dfcfw.com/pdf/H2_{item}_1.pdf" for item in big_df["招股说明书"]
    ]
    big_df = big_df[
        [
            "序号",
            "企业名称",
            "最新状态",
            "注册地",
            "行业",
            "保荐机构",
            "律师事务所",
            "会计师事务所",
            "更新日期",
            "受理日期",
            "拟上市地点",
            "招股说明书",
        ]
    ]
    big_df["更新日期"] = pd.to_datetime(big_df["更新日期"], errors="coerce").dt.date
    big_df["受理日期"] = pd.to_datetime(big_df["受理日期"], errors="coerce").dt.date
    return big_df


def stock_register_sh() -> pd.DataFrame:
    """
    东方财富网-数据中心-新股数据-IPO审核信息-上海主板
    https://data.eastmoney.com/xg/ipo/
    :return: 上海主板
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "UPDATE_DATE,ORG_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_IPO_INFOALLNEW",
        "columns": "SECURITY_CODE,STATE,REG_ADDRESS,INFO_CODE,CSRC_INDUSTRY,ACCEPT_DATE,DECLARE_ORG,"
        "PREDICT_LISTING_MARKET,LAW_FIRM,ACCOUNT_FIRM,ORG_CODE,UPDATE_DATE,RECOMMEND_ORG,IS_REGISTRATION",
        "source": "WEB",
        "client": "WEB",
        "filter": '(PREDICT_LISTING_MARKET="沪主板")',
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.rename(
        columns={
            "index": "序号",
            "DECLARE_ORG": "企业名称",
            "STATE": "最新状态",
            "REG_ADDRESS": "注册地",
            "CSRC_INDUSTRY": "行业",
            "RECOMMEND_ORG": "保荐机构",
            "LAW_FIRM": "律师事务所",
            "ACCOUNT_FIRM": "会计师事务所",
            "UPDATE_DATE": "更新日期",
            "ACCEPT_DATE": "受理日期",
            "PREDICT_LISTING_MARKET": "拟上市地点",
            "INFO_CODE": "招股说明书",
        },
        inplace=True,
    )
    big_df["招股说明书"] = [
        f"https://pdf.dfcfw.com/pdf/H2_{item}_1.pdf" for item in big_df["招股说明书"]
    ]
    big_df = big_df[
        [
            "序号",
            "企业名称",
            "最新状态",
            "注册地",
            "行业",
            "保荐机构",
            "律师事务所",
            "会计师事务所",
            "更新日期",
            "受理日期",
            "拟上市地点",
            "招股说明书",
        ]
    ]
    big_df["更新日期"] = pd.to_datetime(big_df["更新日期"], errors="coerce").dt.date
    big_df["受理日期"] = pd.to_datetime(big_df["受理日期"], errors="coerce").dt.date
    return big_df


def stock_register_sz() -> pd.DataFrame:
    """
    东方财富网-数据中心-新股数据-IPO审核信息-深圳主板
    https://data.eastmoney.com/xg/ipo/
    :return: 深圳主板
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "UPDATE_DATE,ORG_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_IPO_INFOALLNEW",
        "columns": "SECURITY_CODE,STATE,REG_ADDRESS,INFO_CODE,CSRC_INDUSTRY,ACCEPT_DATE,DECLARE_ORG,"
        "PREDICT_LISTING_MARKET,LAW_FIRM,ACCOUNT_FIRM,ORG_CODE,UPDATE_DATE,RECOMMEND_ORG,IS_REGISTRATION",
        "source": "WEB",
        "client": "WEB",
        "filter": '(PREDICT_LISTING_MARKET="深主板")',
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.rename(
        columns={
            "index": "序号",
            "DECLARE_ORG": "企业名称",
            "STATE": "最新状态",
            "REG_ADDRESS": "注册地",
            "CSRC_INDUSTRY": "行业",
            "RECOMMEND_ORG": "保荐机构",
            "LAW_FIRM": "律师事务所",
            "ACCOUNT_FIRM": "会计师事务所",
            "UPDATE_DATE": "更新日期",
            "ACCEPT_DATE": "受理日期",
            "PREDICT_LISTING_MARKET": "拟上市地点",
            "INFO_CODE": "招股说明书",
        },
        inplace=True,
    )
    big_df["招股说明书"] = [
        f"https://pdf.dfcfw.com/pdf/H2_{item}_1.pdf" for item in big_df["招股说明书"]
    ]
    big_df = big_df[
        [
            "序号",
            "企业名称",
            "最新状态",
            "注册地",
            "行业",
            "保荐机构",
            "律师事务所",
            "会计师事务所",
            "更新日期",
            "受理日期",
            "拟上市地点",
            "招股说明书",
        ]
    ]
    big_df["更新日期"] = pd.to_datetime(big_df["更新日期"], errors="coerce").dt.date
    big_df["受理日期"] = pd.to_datetime(big_df["受理日期"], errors="coerce").dt.date
    return big_df


def stock_register_db() -> pd.DataFrame:
    """
    东方财富网-数据中心-新股数据-IPO审核信息-达标企业
    https://data.eastmoney.com/xg/cyb/
    :return: 达标企业
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_KCB_IPO",
        "columns": "KCB_LB",
        "source": "WEB",
        "client": "WEB",
        "filter": '(ORG_TYPE_CODE="03")',
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = range(1, len(big_df) + 1)
    big_df.rename(
        columns={
            "index": "序号",
            "ORG_NAME": "企业名称",
        },
        inplace=True,
    )

    big_df = big_df[
        [
            "序号",
            "企业名称",
        ]
    ]

    return big_df


if __name__ == "__main__":
    pd.set_option("display.max_columns", None)
    stock_register_kcb_df = stock_register_kcb()
    print(stock_register_kcb_df)

    stock_register_cyb_df = stock_register_cyb()
    print(stock_register_cyb_df)

    stock_register_bj_df = stock_register_bj()
    print(stock_register_bj_df)

    stock_register_db_df = stock_register_db()
    print(stock_register_db_df)
