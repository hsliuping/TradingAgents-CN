#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/3 17:08
Desc: 金十数据中心-经济指标-欧元区
金十数据中心-经济指标-欧元区-国民经济运行状况-经济状况
金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平
金十数据中心-经济指标-欧元区-国民经济运行状况-劳动力市场
金十数据中心-经济指标-欧元区-贸易状况
金十数据中心-经济指标-欧元区-产业指标
金十数据中心-经济指标-欧元区-领先指标
"""

import time

import pandas as pd
import requests
from tqdm import tqdm


# 金十数据中心-经济指标-欧元区-国民经济运行状况
# 金十数据中心-经济指标-欧元区-国民经济运行状况-经济状况
# 金十数据中心-经济指标-欧元区-国民经济运行状况-经济状况-欧元区季度GDP年率报告
def macro_euro_gdp_yoy() -> pd.DataFrame:
    """
    欧元区季度 GDP 年率报告, 数据区间从 20131114-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_gdp_yoy
    :return: 欧元区季度 GDP 年率报告
    :rtype: pandas.DataFrame
    """
    ec = 84
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {"category": "ec", "attr_id": ec}
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }

    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)

    big_df["商品"] = "欧元区季度GDP年率"

    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区CPI月率报告
def macro_euro_cpi_mom() -> pd.DataFrame:
    """
    欧元区 CPI 月率报告, 数据区间从 19900301-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_cpi_mom
    https://cdn.jin10.com/dc/reports/dc_eurozone_cpi_mom_all.js?v=1578578318
    :return: 欧元区CPI月率报告
    :rtype: pandas.Series
    """
    ec = 84
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {"category": "ec", "attr_id": ec}
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }

    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区CPI月率"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区CPI年率报告
def macro_euro_cpi_yoy() -> pd.DataFrame:
    """
    欧元区CPI年率报告, 数据区间从19910201-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_cpi_yoy
    https://cdn.jin10.com/dc/reports/dc_eurozone_cpi_yoy_all.js?v=1578578404
    :return: 欧元区CPI年率报告-今值(%)
    :rtype: pandas.Series
    """
    ec = 8
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {
        "category": "ec",
        "attr_id": ec,
    }
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }

    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区CPI年率"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区PPI月率报告
def macro_euro_ppi_mom() -> pd.DataFrame:
    """
    欧元区PPI月率报告, 数据区间从19810301-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_ppi_mom
    https://cdn.jin10.com/dc/reports/dc_eurozone_ppi_mom_all.js?v=1578578493
    :return: 欧元区PPI月率报告-今值(%)
    :rtype: pandas.Series
    """
    ec = 36
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {
        "category": "ec",
        "attr_id": ec,
    }
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }
    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区PPI月率"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区零售销售月率报告
def macro_euro_retail_sales_mom() -> pd.DataFrame:
    """
    欧元区零售销售月率报告, 数据区间从20000301-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_retail_sales_mom
    https://cdn.jin10.com/dc/reports/dc_eurozone_retail_sales_mom_all.js?v=1578578576
    :return: 欧元区零售销售月率报告-今值(%)
    :rtype: pandas.Series
    """
    ec = 38
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {
        "category": "ec",
        "attr_id": ec,
    }
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }

    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区零售销售月率"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-国民经济运行状况-劳动力市场-欧元区季调后就业人数季率报告
def macro_euro_employment_change_qoq() -> pd.DataFrame:
    """
    欧元区季调后就业人数季率报告, 数据区间从20083017-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_employment_change_qoq
    https://cdn.jin10.com/dc/reports/dc_eurozone_employment_change_qoq_all.js?v=1578578699
    :return: 欧元区季调后就业人数季率报告-今值(%)
    :rtype: pandas.Series
    """
    ec = 14
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {"category": "ec", "attr_id": ec}
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }

    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区季调后就业人数季率"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-国民经济运行状况-劳动力市场-欧元区失业率报告
def macro_euro_unemployment_rate_mom() -> pd.DataFrame:
    """
    欧元区失业率报告, 数据区间从19980501-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_unemployment_rate_mom
    https://cdn.jin10.com/dc/reports/dc_eurozone_unemployment_rate_mom_all.js?v=1578578767
    :return: 欧元区失业率报告-今值(%)
    :rtype: pandas.Series
    """
    ec = 46
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {
        "category": "ec",
        "attr_id": ec,
    }
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }

    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区失业率"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-贸易状况-欧元区未季调贸易帐报告
def macro_euro_trade_balance() -> pd.DataFrame:
    """
    欧元区未季调贸易帐报告, 数据区间从19990201-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_trade_balance_mom
    https://cdn.jin10.com/dc/reports/dc_eurozone_trade_balance_mom_all.js?v=1578577862
    :return: 欧元区未季调贸易帐报告-今值(亿欧元)
    :rtype: pandas.Series
    """
    ec = 43
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {
        "category": "ec",
        "attr_id": ec,
    }
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }

    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区未季调贸易帐"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-贸易状况-欧元区经常帐报告
def macro_euro_current_account_mom() -> pd.DataFrame:
    """
    欧元区经常帐报告, 数据区间从20080221-至今, 前两个值需要去掉
    https://datacenter.jin10.com/reportType/dc_eurozone_current_account_mom
    https://cdn.jin10.com/dc/reports/dc_eurozone_current_account_mom_all.js?v=1578577976
    :return: 欧元区经常帐报告-今值(亿欧元)
    :rtype: pandas.Series
    """
    ec = 11
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {
        "category": "ec",
        "attr_id": ec,
    }
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }

    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区经常帐"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-产业指标-欧元区工业产出月率报告
def macro_euro_industrial_production_mom() -> pd.DataFrame:
    """
    欧元区工业产出月率报告, 数据区间从19910301-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_industrial_production_mom
    https://cdn.jin10.com/dc/reports/dc_eurozone_industrial_production_mom_all.js?v=1578577377
    :return: 欧元区工业产出月率报告-今值(%)
    :rtype: pandas.Series
    """
    ec = 19
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {
        "category": "ec",
        "attr_id": ec,
    }
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }

    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区工业产出月率"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-产业指标-欧元区制造业PMI初值报告
def macro_euro_manufacturing_pmi() -> pd.DataFrame:
    """
    欧元区制造业PMI初值报告, 数据区间从20080222-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_manufacturing_pmi
    https://cdn.jin10.com/dc/reports/dc_eurozone_manufacturing_pmi_all.js?v=1578577537
    :return: 欧元区制造业PMI初值报告-今值
    :rtype: pandas.Series
    """
    ec = 30
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {
        "category": "ec",
        "attr_id": ec,
    }
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }

    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区制造业PMI初值"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-产业指标-欧元区服务业PMI终值报告
def macro_euro_services_pmi() -> pd.DataFrame:
    """
    欧元区服务业PMI终值报告, 数据区间从 20080222-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_services_pmi
    https://cdn.jin10.com/dc/reports/dc_eurozone_services_pmi_all.js?v=1578577639
    :return: 欧元区服务业PMI终值报告-今值
    :rtype: pandas.Series
    """
    ec = 41
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {
        "category": "ec",
        "attr_id": ec,
    }
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }

    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区服务业PMI终值"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-领先指标-欧元区ZEW经济景气指数报告
def macro_euro_zew_economic_sentiment() -> pd.DataFrame:
    """
    欧元区ZEW经济景气指数报告, 数据区间从20080212-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_zew_economic_sentiment
    https://cdn.jin10.com/dc/reports/dc_eurozone_zew_economic_sentiment_all.js?v=1578577013
    :return: 欧元区ZEW经济景气指数报告-今值
    :rtype: pandas.Series
    """
    ec = 48
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {
        "category": "ec",
        "attr_id": ec,
    }
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }
    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区ZEW经济景气指数"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-经济指标-欧元区-领先指标-欧元区Sentix投资者信心指数报告
def macro_euro_sentix_investor_confidence() -> pd.DataFrame:
    """
    欧元区Sentix投资者信心指数报告, 数据区间从20020801-至今
    https://datacenter.jin10.com/reportType/dc_eurozone_sentix_investor_confidence
    https://cdn.jin10.com/dc/reports/dc_eurozone_sentix_investor_confidence_all.js?v=1578577195
    :return: 欧元区Sentix投资者信心指数报告-今值
    :rtype: pandas.Series
    """
    ec = 40
    url = "https://datacenter-api.jin10.com/reports/dates"
    params = {
        "category": "ec",
        "attr_id": ec,
    }
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }
    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    date_list = data_json["data"]
    date_point_list = [item for num, item in enumerate(date_list) if num % 20 == 0]
    big_df = pd.DataFrame()
    for date in tqdm(date_point_list, leave=False):
        url = "https://datacenter-api.jin10.com/reports/list_v2"
        params = {
            "max_date": f"{date}",
            "category": "ec",
            "attr_id": ec,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        }
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            data_json["data"]["values"],
            columns=[item["name"] for item in data_json["data"]["keys"]],
        )
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df["商品"] = "欧元区Sentix投资者信心指数"
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]
    big_df["今值"] = pd.to_numeric(big_df["今值"])
    big_df["预测值"] = pd.to_numeric(big_df["预测值"])
    big_df["前值"] = pd.to_numeric(big_df["前值"])
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-伦敦金属交易所(LME)-持仓报告
def macro_euro_lme_holding() -> pd.DataFrame:
    """
    伦敦金属交易所(LME)-持仓报告, 数据区间从 20151022-至今
    https://datacenter.jin10.com/reportType/dc_lme_traders_report
    https://cdn.jin10.com/data_center/reports/lme_position.json?_=1591533934658
    :return: 伦敦金属交易所(LME)-持仓报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {"_": str(int(round(t * 1000)))}
    r = requests.get(
        url="https://cdn.jin10.com/data_center/reports/lme_position.json", params=params
    )
    json_data = r.json()
    temp_df = pd.DataFrame(json_data["values"]).T
    temp_df.fillna(value="[0, 0, 0]", inplace=True)
    big_df = pd.DataFrame()
    for item in temp_df.columns:
        for i in range(3):
            inner_temp_df = temp_df.loc[:, item].apply(lambda x: eval(str(x))[i])
            inner_temp_df.name = inner_temp_df.name + "-" + json_data["keys"][i]["name"]
            big_df = pd.concat(objs=[big_df, inner_temp_df], axis=1)
    big_df = big_df.astype("float")
    big_df = big_df.iloc[:-1, :].copy()
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    big_df.sort_values(by=["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-伦敦金属交易所(LME)-库存报告
def macro_euro_lme_stock() -> pd.DataFrame:
    """
    伦敦金属交易所(LME)-库存报告, 数据区间从 20140702-至今
    https://datacenter.jin10.com/reportType/dc_lme_report
    https://cdn.jin10.com/data_center/reports/lme_stock.json?_=1591535304783
    :return: 伦敦金属交易所(LME)-库存报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {"_": str(int(round(t * 1000)))}
    r = requests.get(
        url="https://cdn.jin10.com/data_center/reports/lme_stock.json", params=params
    )
    json_data = r.json()
    temp_df = pd.DataFrame(json_data["values"]).T
    big_df = pd.DataFrame()
    for item in temp_df.columns:
        for i in range(3):
            inner_temp_df = temp_df.loc[:, item].apply(lambda x: eval(str(x))[i])
            inner_temp_df.name = inner_temp_df.name + "-" + json_data["keys"][i]["name"]
            big_df = pd.concat(objs=[big_df, inner_temp_df], axis=1)
    big_df.sort_index(inplace=True)
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    return big_df


if __name__ == "__main__":
    # 金十数据中心-经济指标-欧元区-国民经济运行状况
    # 金十数据中心-经济指标-欧元区-国民经济运行状况-经济状况
    # 金十数据中心-经济指标-欧元区-国民经济运行状况-经济状况-欧元区季度GDP年率报告
    macro_euro_gdp_yoy_df = macro_euro_gdp_yoy()
    print(macro_euro_gdp_yoy_df)

    # 金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平
    # 金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区CPI月率报告
    macro_euro_cpi_mom_df = macro_euro_cpi_mom()
    print(macro_euro_cpi_mom_df)
    # 金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区CPI年率报告
    macro_euro_cpi_yoy_df = macro_euro_cpi_yoy()
    print(macro_euro_cpi_yoy_df)
    # 金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区PPI月率报告
    macro_euro_ppi_mom_df = macro_euro_ppi_mom()
    print(macro_euro_ppi_mom_df)
    # 金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区零售销售月率报告
    macro_euro_retail_sales_mom_df = macro_euro_retail_sales_mom()
    print(macro_euro_retail_sales_mom_df)

    # 金十数据中心-经济指标-欧元区-国民经济运行状况-劳动力市场
    # 金十数据中心-经济指标-欧元区-国民经济运行状况-劳动力市场-欧元区季调后就业人数季率报告
    macro_euro_employment_change_qoq_df = macro_euro_employment_change_qoq()
    print(macro_euro_employment_change_qoq_df)
    # 金十数据中心-经济指标-欧元区-国民经济运行状况-劳动力市场-欧元区失业率报告
    macro_euro_unemployment_rate_mom_df = macro_euro_unemployment_rate_mom()
    print(macro_euro_unemployment_rate_mom_df)
    # 金十数据中心-经济指标-欧元区-贸易状况
    # 金十数据中心-经济指标-欧元区-贸易状况-欧元区未季调贸易帐报告
    macro_euro_trade_balance_df = macro_euro_trade_balance()
    print(macro_euro_trade_balance_df)
    # 金十数据中心-经济指标-欧元区-贸易状况-欧元区经常帐报告
    macro_euro_current_account_mom_df = macro_euro_current_account_mom()
    print(macro_euro_current_account_mom_df)
    # 金十数据中心-经济指标-欧元区-产业指标
    # 金十数据中心-经济指标-欧元区-产业指标-欧元区工业产出月率报告
    macro_euro_industrial_production_mom_df = macro_euro_industrial_production_mom()
    print(macro_euro_industrial_production_mom_df)
    # 金十数据中心-经济指标-欧元区-产业指标-欧元区制造业PMI初值报告
    macro_euro_manufacturing_pmi_df = macro_euro_manufacturing_pmi()
    print(macro_euro_manufacturing_pmi_df)

    # 金十数据中心-经济指标-欧元区-产业指标-欧元区服务业PMI终值报告
    macro_euro_services_pmi_df = macro_euro_services_pmi()
    print(macro_euro_services_pmi_df)

    # 金十数据中心-经济指标-欧元区-领先指标
    # 金十数据中心-经济指标-欧元区-领先指标-欧元区ZEW经济景气指数报告
    macro_euro_zew_economic_sentiment_df = macro_euro_zew_economic_sentiment()
    print(macro_euro_zew_economic_sentiment_df)

    # 金十数据中心-经济指标-欧元区-领先指标-欧元区Sentix投资者信心指数报告
    macro_euro_sentix_investor_confidence_df = macro_euro_sentix_investor_confidence()
    print(macro_euro_sentix_investor_confidence_df)

    # 金十数据中心-伦敦金属交易所(LME)-持仓报告
    macro_euro_lme_holding_df = macro_euro_lme_holding()
    print(macro_euro_lme_holding_df)

    # 金十数据中心-伦敦金属交易所(LME)-库存报告
    macro_euro_lme_stock_df = macro_euro_lme_stock()
    print(macro_euro_lme_stock_df)
