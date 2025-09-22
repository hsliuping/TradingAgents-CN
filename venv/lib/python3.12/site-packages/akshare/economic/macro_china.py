#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/12/2 15:20
Desc: 宏观数据-中国
"""

import datetime
import json
import math
import time

import pandas as pd
import requests

from akshare.economic.cons import (
    JS_CHINA_ENERGY_DAILY_URL,
)
from akshare.utils import demjson
from akshare.utils.tqdm import get_tqdm


def __macro_china_base_func(symbol: str, params: dict) -> pd.DataFrame:
    """
    金十数据中心-经济指标-美国-基础函数
    https://datacenter.jin10.com/economic
    :return: 美国经济指标数据
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }
    url = "https://datacenter-api.jin10.com/reports/list_v2"
    params = params
    big_df = pd.DataFrame()
    while True:
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        if not data_json["data"]["values"]:
            break
        temp_df = pd.DataFrame(data_json["data"]["values"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
        last_date_str = temp_df.iat[-1, 0]
        last_date_str = (
            (
                datetime.datetime.strptime(last_date_str, "%Y-%m-%d")
                - datetime.timedelta(days=1)
            )
            .date()
            .isoformat()
        )
        params.update({"max_date": f"{last_date_str}"})
    big_df.columns = [
        "日期",
        "今值",
        "预测值",
        "前值",
    ]
    big_df["商品"] = symbol
    big_df = big_df[
        [
            "商品",
            "日期",
            "今值",
            "预测值",
            "前值",
        ]
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["今值"] = pd.to_numeric(big_df["今值"], errors="coerce")
    big_df["预测值"] = pd.to_numeric(big_df["预测值"], errors="coerce")
    big_df["前值"] = pd.to_numeric(big_df["前值"], errors="coerce")
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


# 企业商品价格指数
def macro_china_qyspjg() -> pd.DataFrame:
    """
    东方财富-经济数据一览-中国-企业商品价格指数
    https://data.eastmoney.com/cjsj/qyspjg.html
    :return: 企业商品价格指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,BASE,BASE_SAME,BASE_SEQUENTIAL,FARM_BASE,FARM_BASE_SAME,"
        "FARM_BASE_SEQUENTIAL,MINERAL_BASE,MINERAL_BASE_SAME,MINERAL_BASE_SEQUENTIAL,"
        "ENERGY_BASE,ENERGY_BASE_SAME,ENERGY_BASE_SEQUENTIAL",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_GOODS_INDEX",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.rename(
        columns={
            "REPORT_DATE": "-",
            "TIME": "月份",
            "BASE": "总指数-指数值",
            "BASE_SAME": "总指数-同比增长",
            "BASE_SEQUENTIAL": "总指数-环比增长",
            "FARM_BASE": "农产品-指数值",
            "FARM_BASE_SAME": "农产品-同比增长",
            "FARM_BASE_SEQUENTIAL": "农产品-环比增长",
            "MINERAL_BASE": "矿产品-指数值",
            "MINERAL_BASE_SAME": "矿产品-同比增长",
            "MINERAL_BASE_SEQUENTIAL": "矿产品-环比增长",
            "ENERGY_BASE": "煤油电-指数值",
            "ENERGY_BASE_SAME": "煤油电-同比增长",
            "ENERGY_BASE_SEQUENTIAL": "煤油电-环比增长",
        },
        inplace=True,
    )

    temp_df = temp_df[
        [
            "月份",
            "总指数-指数值",
            "总指数-同比增长",
            "总指数-环比增长",
            "农产品-指数值",
            "农产品-同比增长",
            "农产品-环比增长",
            "矿产品-指数值",
            "矿产品-同比增长",
            "矿产品-环比增长",
            "煤油电-指数值",
            "煤油电-同比增长",
            "煤油电-环比增长",
        ]
    ]
    temp_df["总指数-指数值"] = pd.to_numeric(temp_df["总指数-指数值"], errors="coerce")
    temp_df["总指数-同比增长"] = pd.to_numeric(
        temp_df["总指数-同比增长"], errors="coerce"
    )
    temp_df["总指数-环比增长"] = pd.to_numeric(
        temp_df["总指数-环比增长"], errors="coerce"
    )
    temp_df["农产品-指数值"] = pd.to_numeric(temp_df["农产品-指数值"], errors="coerce")
    temp_df["农产品-同比增长"] = pd.to_numeric(
        temp_df["农产品-同比增长"], errors="coerce"
    )
    temp_df["农产品-环比增长"] = pd.to_numeric(
        temp_df["农产品-环比增长"], errors="coerce"
    )
    temp_df["矿产品-指数值"] = pd.to_numeric(temp_df["矿产品-指数值"], errors="coerce")
    temp_df["矿产品-同比增长"] = pd.to_numeric(
        temp_df["矿产品-同比增长"], errors="coerce"
    )
    temp_df["矿产品-环比增长"] = pd.to_numeric(
        temp_df["矿产品-环比增长"], errors="coerce"
    )
    temp_df["煤油电-指数值"] = pd.to_numeric(temp_df["煤油电-指数值"], errors="coerce")
    temp_df["煤油电-同比增长"] = pd.to_numeric(
        temp_df["煤油电-同比增长"], errors="coerce"
    )
    temp_df["煤油电-环比增长"] = pd.to_numeric(
        temp_df["煤油电-环比增长"], errors="coerce"
    )
    return temp_df


# 外商直接投资数据
def macro_china_fdi() -> pd.DataFrame:
    """
    东方财富-经济数据一览-中国-外商直接投资数据
    https://data.eastmoney.com/cjsj/fdi.html
    :return: 外商直接投资数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,ACTUAL_FOREIGN,ACTUAL_FOREIGN_SAME,ACTUAL_FOREIGN_SEQUENTIAL,"
        "ACTUAL_FOREIGN_ACCUMULATE,FOREIGN_ACCUMULATE_SAME",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_FDI",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])

    temp_df.columns = [
        "-",
        "月份",
        "当月",
        "当月-同比增长",
        "当月-环比增长",
        "累计",
        "累计-同比增长",
    ]
    temp_df = temp_df[
        [
            "月份",
            "当月",
            "当月-同比增长",
            "当月-环比增长",
            "累计",
            "累计-同比增长",
        ]
    ]
    temp_df["当月"] = pd.to_numeric(temp_df["当月"], errors="coerce")
    temp_df["当月-同比增长"] = pd.to_numeric(temp_df["当月-同比增长"], errors="coerce")
    temp_df["当月-环比增长"] = pd.to_numeric(temp_df["当月-环比增长"], errors="coerce")
    temp_df["累计"] = pd.to_numeric(temp_df["累计"], errors="coerce")
    temp_df["累计-同比增长"] = pd.to_numeric(temp_df["累计-同比增长"], errors="coerce")
    temp_df.sort_values(["月份"], ignore_index=True, inplace=True)
    return temp_df


# 中国社会融资规模数据
def macro_china_shrzgm() -> pd.DataFrame:
    """
    商务数据中心-国内贸易-社会融资规模增量统计
    https://data.mofcom.gov.cn/gnmy/shrzgm.shtml
    :return: 社会融资规模增量统计
    :rtype: pandas.DataFrame
    """
    url = "http://data.mofcom.gov.cn/datamofcom/front/gnmy/shrzgmQuery"
    r = requests.post(url)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json)
    temp_df.columns = [
        "月份",
        "其中-未贴现银行承兑汇票",
        "其中-委托贷款",
        "其中-委托贷款外币贷款",
        "其中-人民币贷款",
        "其中-企业债券",
        "社会融资规模增量",
        "其中-非金融企业境内股票融资",
        "其中-信托贷款",
    ]
    temp_df = temp_df[
        [
            "月份",
            "社会融资规模增量",
            "其中-人民币贷款",
            "其中-委托贷款外币贷款",
            "其中-委托贷款",
            "其中-信托贷款",
            "其中-未贴现银行承兑汇票",
            "其中-企业债券",
            "其中-非金融企业境内股票融资",
        ]
    ]
    temp_df["社会融资规模增量"] = pd.to_numeric(
        temp_df["社会融资规模增量"], errors="coerce"
    )
    temp_df["其中-人民币贷款"] = pd.to_numeric(
        temp_df["其中-人民币贷款"], errors="coerce"
    )
    temp_df["其中-委托贷款外币贷款"] = pd.to_numeric(
        temp_df["其中-委托贷款外币贷款"], errors="coerce"
    )
    temp_df["其中-委托贷款"] = pd.to_numeric(temp_df["其中-委托贷款"], errors="coerce")
    temp_df["其中-信托贷款"] = pd.to_numeric(temp_df["其中-信托贷款"], errors="coerce")
    temp_df["其中-未贴现银行承兑汇票"] = pd.to_numeric(
        temp_df["其中-未贴现银行承兑汇票"], errors="coerce"
    )
    temp_df["其中-企业债券"] = pd.to_numeric(temp_df["其中-企业债券"], errors="coerce")
    temp_df["其中-非金融企业境内股票融资"] = pd.to_numeric(
        temp_df["其中-非金融企业境内股票融资"], errors="coerce"
    )
    temp_df.sort_values(["月份"], inplace=True)
    temp_df.reset_index(drop=True, inplace=True)
    return temp_df


def macro_china_urban_unemployment() -> pd.DataFrame:
    """
    国家统计局-月度数据-城镇调查失业率
    https://data.stats.gov.cn/easyquery.htm?cn=A01&zb=A0203&sj=202304
    :return: 城镇调查失业率
    :rtype: pandas.DataFrame
    """
    url = "https://data.stats.gov.cn/easyquery.htm"
    params = {
        "m": "QueryData",
        "dbcode": "hgyd",
        "rowcode": "zb",
        "colcode": "sj",
        "wds": "[]",
        "dfwds": '[{"wdcode":"zb","valuecode":"A0E01"},{"wdcode":"sj","valuecode":"LAST72"}]',
        "k1": "1691326382042",
        "h": "1",
    }
    r = requests.get(url, params=params, verify=False)
    r.encoding = "utf-8"
    data_json = r.json()
    value_list = [item["data"]["data"] for item in data_json["returndata"]["datanodes"]]
    name_list = [
        item["wds"][0]["valuecode"] for item in data_json["returndata"]["datanodes"]
    ]
    date_list = [
        item["wds"][1]["valuecode"] for item in data_json["returndata"]["datanodes"]
    ]
    temp_df = pd.DataFrame(data_json["returndata"]["wdnodes"][0]["nodes"])
    code_item_map = dict(zip(temp_df["code"], temp_df["cname"]))
    temp_df = pd.DataFrame([date_list, name_list, value_list]).T
    temp_df.columns = ["date", "item", "value"]
    temp_df["item"] = temp_df["item"].map(code_item_map)
    temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
    temp_df.sort_values(by=["date"], ignore_index=True, inplace=True)
    return temp_df


# 金十数据中心-经济指标-中国-国民经济运行状况-经济状况-中国GDP年率报告
def macro_china_gdp_yearly() -> pd.DataFrame:
    """
    金十数据中心-中国 GDP 年率报告, 数据区间从 20110120-至今
    https://datacenter.jin10.com/reportType/dc_chinese_gdp_yoy
    :return: 中国 GDP 年率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "57",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(symbol="中国GDP年率报告", params=params)
    return temp_df


# 金十数据中心-经济指标-中国-国民经济运行状况-物价水平-中国CPI年率报告
def macro_china_cpi_yearly() -> pd.DataFrame:
    """
    中国年度 CPI 数据, 数据区间从 19860201-至今
    https://datacenter.jin10.com/reportType/dc_chinese_cpi_yoy
    :return: 中国年度 CPI 数据
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "56",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(symbol="中国CPI年率报告", params=params)
    return temp_df


# 金十数据中心-经济指标-中国-国民经济运行状况-物价水平-中国CPI月率报告
def macro_china_cpi_monthly() -> pd.DataFrame:
    """
    中国月度 CPI 数据, 数据区间从 19960201-至今
    https://datacenter.jin10.com/reportType/dc_chinese_cpi_mom
    :return: 中国月度 CPI 数据
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "72",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(symbol="中国CPI月率报告", params=params)
    return temp_df


# 金十数据中心-经济指标-中国-国民经济运行状况-物价水平-中国PPI年率报告
def macro_china_ppi_yearly() -> pd.DataFrame:
    """
    中国年度 PPI 数据, 数据区间从 19950801-至今
    https://datacenter.jin10.com/reportType/dc_chinese_ppi_yoy
    :return: 中国年度 PPI 数据
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "60",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(symbol="中国PPI年率报告", params=params)
    return temp_df


# 金十数据中心-经济指标-中国-贸易状况-以美元计算出口年率报告
def macro_china_exports_yoy() -> pd.DataFrame:
    """
    中国以美元计算出口年率报告, 数据区间从 19820201-至今
    https://datacenter.jin10.com/reportType/dc_chinese_exports_yoy
    :return: 中国以美元计算出口年率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "66",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(
        symbol="中国以美元计算出口年率报告", params=params
    )
    return temp_df


# 金十数据中心-经济指标-中国-贸易状况-以美元计算进口年率
def macro_china_imports_yoy() -> pd.DataFrame:
    """
    中国以美元计算进口年率报告, 数据区间从 19960201-至今
    https://datacenter.jin10.com/reportType/dc_chinese_imports_yoy
    https://cdn.jin10.com/dc/reports/dc_chinese_imports_yoy_all.js?v=1578754588
    :return: 中国以美元计算进口年率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "77",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(
        symbol="中国以美元计算进口年率报告", params=params
    )
    return temp_df


# 金十数据中心-经济指标-中国-贸易状况-以美元计算贸易帐(亿美元)
def macro_china_trade_balance() -> pd.DataFrame:
    """
    中国以美元计算贸易帐报告, 数据区间从 19810201-至今
    https://datacenter.jin10.com/reportType/dc_chinese_trade_balance
    https://cdn.jin10.com/dc/reports/dc_chinese_trade_balance_all.js?v=1578754677
    :return: 中国以美元计算贸易帐报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "61",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(symbol="中国以美元计算贸易帐报告", params=params)
    return temp_df


# 金十数据中心-经济指标-中国-产业指标-规模以上工业增加值年率
def macro_china_industrial_production_yoy() -> pd.DataFrame:
    """
    中国规模以上工业增加值年率报告, 数据区间从19900301-至今
    https://datacenter.jin10.com/reportType/dc_chinese_industrial_production_yoy
    https://cdn.jin10.com/dc/reports/dc_chinese_industrial_production_yoy_all.js?v=1578754779
    :return: 中国规模以上工业增加值年率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "58",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(
        symbol="中国规模以上工业增加值年率报告", params=params
    )
    return temp_df


# 金十数据中心-经济指标-中国-产业指标-官方制造业PMI
def macro_china_pmi_yearly() -> pd.DataFrame:
    """
    中国年度 PMI 数据, 数据区间从 20050201-至今
    https://datacenter.jin10.com/reportType/dc_chinese_manufacturing_pmi
    :return: 中国年度 PMI 数据
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {
        "category": "ec",
        "attr_id": "65",
        "max_date": "",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(symbol="中国官方制造业PMI", params=params)
    return temp_df


# 金十数据中心-经济指标-中国-产业指标-财新制造业PMI终值
def macro_china_cx_pmi_yearly() -> pd.DataFrame:
    """
    中国年度财新 PMI 数据, 数据区间从 20120120-至今
    https://datacenter.jin10.com/reportType/dc_chinese_caixin_manufacturing_pmi
    :return: 中国年度财新 PMI 数据
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "73",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(symbol="中国财新制造业PMI终值报告", params=params)
    return temp_df


# 金十数据中心-经济指标-中国-产业指标-财新服务业PMI
def macro_china_cx_services_pmi_yearly() -> pd.DataFrame:
    """
    中国财新服务业PMI报告, 数据区间从 20120405-至今
    https://datacenter.jin10.com/reportType/dc_chinese_caixin_services_pmi
    https://cdn.jin10.com/dc/reports/dc_chinese_caixin_services_pmi_all.js?v=1578818109
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "67",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(symbol="中国财新服务业PMI报告", params=params)
    return temp_df


# 金十数据中心-经济指标-中国-产业指标-中国官方非制造业PMI
def macro_china_non_man_pmi() -> pd.DataFrame:
    """
    中国官方非制造业 PMI, 数据区间从 20160101-至今
    https://datacenter.jin10.com/reportType/dc_chinese_non_manufacturing_pmi
    :return: 中国官方非制造业 PMI
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "75",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(symbol="中国官方非制造业PMI报告", params=params)
    return temp_df


# 金十数据中心-经济指标-中国-金融指标-外汇储备(亿美元)
def macro_china_fx_reserves_yearly() -> pd.DataFrame:
    """
    中国年度外汇储备数据, 数据区间从 20140115-至今
    https://datacenter.jin10.com/reportType/dc_chinese_fx_reserves
    :return: 中国年度外汇储备数据
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "76",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(symbol="中国外汇储备报告", params=params)
    return temp_df


# 金十数据中心-经济指标-中国-金融指标-M2货币供应年率
def macro_china_m2_yearly() -> pd.DataFrame:
    """
    中国年度 M2 数据, 数据区间从 19980201-至今
    https://datacenter.jin10.com/reportType/dc_chinese_m2_money_supply_yoy
    :return: 中国年度 M2 数据
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "59",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_china_base_func(symbol="中国M2货币供应年率报告", params=params)
    return temp_df


# 金十数据中心-经济指标-中国-金融指标-上海银行业同业拆借报告
def macro_china_shibor_all() -> pd.DataFrame:
    """
    上海银行业同业拆借报告, 数据区间从20170317-至今
    https://datacenter.jin10.com/reportType/dc_shibor
    https://cdn.jin10.com/dc/reports/dc_shibor_all.js?v=1578755058
    :return: 上海银行业同业拆借报告-今值(%)
    :rtype: pandas.DataFrame
    """
    import numpy as np

    t = time.time()
    params = {"_": t}
    res = requests.get(
        url="https://cdn.jin10.com/data_center/reports/il_1.json", params=params
    )
    json_data = res.json()
    temp_df = pd.DataFrame(json_data["values"]).T
    big_df = pd.DataFrame()
    temp_df.fillna(value="--", inplace=True)
    big_df["O/N-定价"] = temp_df["O/N"].apply(lambda x: x[0])
    big_df["O/N-涨跌幅"] = temp_df["O/N"].apply(lambda x: x[1])
    big_df["1W-定价"] = temp_df["1W"].apply(lambda x: x[0])
    big_df["1W-涨跌幅"] = temp_df["1W"].apply(lambda x: x[1])
    big_df["2W-定价"] = temp_df["2W"].apply(lambda x: x[0])
    big_df["2W-涨跌幅"] = temp_df["2W"].apply(lambda x: x[1])
    big_df["1M-定价"] = temp_df["1M"].apply(lambda x: x[0])
    big_df["1M-涨跌幅"] = temp_df["1M"].apply(lambda x: x[1])
    big_df["3M-定价"] = temp_df["3M"].apply(lambda x: x[0])
    big_df["3M-涨跌幅"] = temp_df["3M"].apply(lambda x: x[1])
    big_df["6M-定价"] = temp_df["6M"].apply(lambda x: x[0])
    big_df["6M-涨跌幅"] = temp_df["6M"].apply(lambda x: x[1])
    big_df["9M-定价"] = temp_df["9M"].apply(lambda x: x[0])
    big_df["9M-涨跌幅"] = temp_df["9M"].apply(lambda x: x[1])
    big_df["1Y-定价"] = temp_df["1Y"].apply(lambda x: x[0])
    big_df["1Y-涨跌幅"] = temp_df["1Y"].apply(lambda x: x[1])
    big_df = big_df.apply(lambda x: x.replace("-", np.nan))
    big_df = big_df.apply(lambda x: x.replace([None], np.nan))
    for item in big_df.columns:
        big_df[item] = pd.to_numeric(big_df[item], errors="coerce")
    big_df.sort_index(inplace=True)
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    return big_df


# 金十数据中心-经济指标-中国-金融指标-人民币香港银行同业拆息
def macro_china_hk_market_info() -> pd.DataFrame:
    """
    香港同业拆借报告, 数据区间从 20170320-至今
    https://datacenter.jin10.com/reportType/dc_hk_market_info
    https://cdn.jin10.com/dc/reports/dc_hk_market_info_all.js?v=1578755471
    :return: 香港同业拆借报告-今值(%)
    :rtype: pandas.DataFrame
    """
    import numpy as np

    t = time.time()
    params = {"_": t}
    res = requests.get(
        url="https://cdn.jin10.com/data_center/reports/il_2.json", params=params
    )
    json_data = res.json()
    temp_df = pd.DataFrame(json_data["values"]).T
    big_df = pd.DataFrame()
    temp_df.fillna(value="--", inplace=True)
    big_df["1W-定价"] = temp_df["1W"].apply(lambda x: x[0])
    big_df["1W-涨跌幅"] = temp_df["1W"].apply(lambda x: x[1])
    big_df["2W-定价"] = temp_df["2W"].apply(lambda x: x[0])
    big_df["2W-涨跌幅"] = temp_df["2W"].apply(lambda x: x[1])
    big_df["1M-定价"] = temp_df["1M"].apply(lambda x: x[0])
    big_df["1M-涨跌幅"] = temp_df["1M"].apply(lambda x: x[1])
    big_df["3M-定价"] = temp_df["3M"].apply(lambda x: x[0])
    big_df["3M-涨跌幅"] = temp_df["3M"].apply(lambda x: x[1])
    big_df["6M-定价"] = temp_df["6M"].apply(lambda x: x[0])
    big_df["6M-涨跌幅"] = temp_df["6M"].apply(lambda x: x[1])
    big_df["1Y-定价"] = temp_df["1Y"].apply(lambda x: x[0])
    big_df["1Y-涨跌幅"] = temp_df["1Y"].apply(lambda x: x[1])
    big_df["ON-定价"] = temp_df["ON"].apply(lambda x: x[0])
    big_df["ON-涨跌幅"] = temp_df["ON"].apply(lambda x: x[1])
    big_df["2M-定价"] = temp_df["2M"].apply(lambda x: x[0])
    big_df["2M-涨跌幅"] = temp_df["2M"].apply(lambda x: x[1])
    big_df = big_df.apply(lambda x: x.replace("-", np.nan))
    big_df = big_df.apply(lambda x: x.replace([None], np.nan))
    for item in big_df.columns:
        big_df[item] = pd.to_numeric(big_df[item], errors="coerce")
    big_df.sort_index(inplace=True)
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    return big_df


# 金十数据中心-经济指标-中国-其他-中国日度沿海六大电库存数据
def macro_china_daily_energy() -> pd.DataFrame:
    """
    中国日度沿海六大电库存数据, 数据区间从20160101-至今
    https://datacenter.jin10.com/reportType/dc_qihuo_energy_report
    :return: pandas.DataFrame
    """
    t = time.time()
    res = requests.get(
        JS_CHINA_ENERGY_DAILY_URL.format(
            str(int(round(t * 1000))), str(int(round(t * 1000)) + 90)
        )
    )
    json_data = json.loads(res.text[res.text.find("{") : res.text.rfind("}") + 1])
    date_list = [item["date"] for item in json_data["list"]]
    value_list = [
        item["datas"]["沿海六大电厂库存动态报告"] for item in json_data["list"]
    ]
    value_df = pd.DataFrame(value_list)
    value_df.columns = json_data["kinds"]
    value_df.index = pd.to_datetime(date_list)
    temp_df = value_df[["沿海六大电库存", "日耗", "存煤可用天数"]]
    temp_df.name = "energy"
    temp_df = temp_df.astype(float)
    temp_df.reset_index(inplace=True)
    temp_df.rename(columns={"index": "日期"}, inplace=True)
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    return temp_df


# 金十数据中心-经济指标-中国-其他-中国人民币汇率中间价报告
def macro_china_rmb() -> pd.DataFrame:
    """
    中国人民币汇率中间价报告, 数据区间从 20170103-至今
    https://datacenter.jin10.com/reportType/dc_rmb_data
    :return: 中国人民币汇率中间价报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {"_": t}
    res = requests.get(
        "https://cdn.jin10.com/data_center/reports/exchange_rate.json",
        params=params,
    )
    json_data = res.json()
    temp_df = pd.DataFrame(json_data["values"]).T
    big_df = pd.DataFrame()
    temp_df.fillna(value="--", inplace=True)
    big_df["美元/人民币_中间价"] = temp_df["美元/人民币"].apply(lambda x: x[0])
    big_df["美元/人民币_涨跌幅"] = temp_df["美元/人民币"].apply(lambda x: x[1])
    big_df["欧元/人民币_中间价"] = temp_df["欧元/人民币"].apply(lambda x: x[0])
    big_df["欧元/人民币_涨跌幅"] = temp_df["欧元/人民币"].apply(lambda x: x[1])
    big_df["100日元/人民币_中间价"] = temp_df["100日元/人民币"].apply(lambda x: x[0])
    big_df["100日元/人民币_涨跌幅"] = temp_df["100日元/人民币"].apply(lambda x: x[1])
    big_df["港元/人民币_中间价"] = temp_df["港元/人民币"].apply(lambda x: x[0])
    big_df["港元/人民币_涨跌幅"] = temp_df["港元/人民币"].apply(lambda x: x[1])
    big_df["英镑/人民币_中间价"] = temp_df["英镑/人民币"].apply(lambda x: x[0])
    big_df["英镑/人民币_涨跌幅"] = temp_df["英镑/人民币"].apply(lambda x: x[1])
    big_df["澳元/人民币_中间价"] = temp_df["澳元/人民币"].apply(lambda x: x[0])
    big_df["澳元/人民币_涨跌幅"] = temp_df["澳元/人民币"].apply(lambda x: x[1])
    big_df["新西兰元/人民币_中间价"] = temp_df["新西兰元/人民币"].apply(lambda x: x[0])
    big_df["新西兰元/人民币_涨跌幅"] = temp_df["新西兰元/人民币"].apply(lambda x: x[1])
    big_df["新加坡元/人民币_中间价"] = temp_df["新加坡元/人民币"].apply(lambda x: x[0])
    big_df["新加坡元/人民币_涨跌幅"] = temp_df["新加坡元/人民币"].apply(lambda x: x[1])
    big_df["瑞郎/人民币_中间价"] = temp_df["瑞郎/人民币"].apply(lambda x: x[0])
    big_df["瑞郎/人民币_涨跌幅"] = temp_df["瑞郎/人民币"].apply(lambda x: x[1])
    big_df["加元/人民币_中间价"] = temp_df["加元/人民币"].apply(lambda x: x[0])
    big_df["加元/人民币_涨跌幅"] = temp_df["加元/人民币"].apply(lambda x: x[1])
    big_df["人民币/马来西亚林吉特_中间价"] = temp_df["人民币/马来西亚林吉特"].apply(
        lambda x: x[0]
    )
    big_df["人民币/马来西亚林吉特_涨跌幅"] = temp_df["人民币/马来西亚林吉特"].apply(
        lambda x: x[1]
    )
    big_df["人民币/俄罗斯卢布_中间价"] = temp_df["人民币/俄罗斯卢布"].apply(
        lambda x: x[0]
    )
    big_df["人民币/俄罗斯卢布_涨跌幅"] = temp_df["人民币/俄罗斯卢布"].apply(
        lambda x: x[1]
    )
    big_df["人民币/南非兰特_中间价"] = temp_df["人民币/南非兰特"].apply(lambda x: x[0])
    big_df["人民币/南非兰特_涨跌幅"] = temp_df["人民币/南非兰特"].apply(lambda x: x[1])
    big_df["人民币/韩元_中间价"] = temp_df["人民币/韩元"].apply(lambda x: x[0])
    big_df["人民币/韩元_涨跌幅"] = temp_df["人民币/韩元"].apply(lambda x: x[1])
    big_df["人民币/阿联酋迪拉姆_中间价"] = temp_df["人民币/阿联酋迪拉姆"].apply(
        lambda x: x[0]
    )
    big_df["人民币/阿联酋迪拉姆_涨跌幅"] = temp_df["人民币/阿联酋迪拉姆"].apply(
        lambda x: x[1]
    )
    big_df["人民币/沙特里亚尔_中间价"] = temp_df["人民币/沙特里亚尔"].apply(
        lambda x: x[0]
    )
    big_df["人民币/沙特里亚尔_涨跌幅"] = temp_df["人民币/沙特里亚尔"].apply(
        lambda x: x[1]
    )
    big_df["人民币/匈牙利福林_中间价"] = temp_df["人民币/匈牙利福林"].apply(
        lambda x: x[0]
    )
    big_df["人民币/匈牙利福林_涨跌幅"] = temp_df["人民币/匈牙利福林"].apply(
        lambda x: x[1]
    )
    big_df["人民币/波兰兹罗提_中间价"] = temp_df["人民币/波兰兹罗提"].apply(
        lambda x: x[0]
    )
    big_df["人民币/波兰兹罗提_涨跌幅"] = temp_df["人民币/波兰兹罗提"].apply(
        lambda x: x[1]
    )
    big_df["人民币/丹麦克朗_中间价"] = temp_df["人民币/丹麦克朗"].apply(lambda x: x[0])
    big_df["人民币/丹麦克朗_涨跌幅"] = temp_df["人民币/丹麦克朗"].apply(lambda x: x[1])
    big_df["人民币/瑞典克朗_中间价"] = temp_df["人民币/瑞典克朗"].apply(lambda x: x[0])
    big_df["人民币/瑞典克朗_涨跌幅"] = temp_df["人民币/瑞典克朗"].apply(lambda x: x[1])
    big_df["人民币/挪威克朗_中间价"] = temp_df["人民币/挪威克朗"].apply(lambda x: x[0])
    big_df["人民币/挪威克朗_涨跌幅"] = temp_df["人民币/挪威克朗"].apply(lambda x: x[1])
    big_df["人民币/土耳其里拉_中间价"] = temp_df["人民币/土耳其里拉"].apply(
        lambda x: x[0]
    )
    big_df["人民币/土耳其里拉_涨跌幅"] = temp_df["人民币/土耳其里拉"].apply(
        lambda x: x[1]
    )
    big_df["人民币/墨西哥比索_中间价"] = temp_df["人民币/墨西哥比索"].apply(
        lambda x: x[0]
    )
    big_df["人民币/墨西哥比索_涨跌幅"] = temp_df["人民币/墨西哥比索"].apply(
        lambda x: x[1]
    )
    big_df["人民币/泰铢_定价"] = temp_df["人民币/泰铢"].apply(lambda x: x[0])
    big_df["人民币/泰铢_涨跌幅"] = temp_df["人民币/泰铢"].apply(lambda x: x[1])
    big_df = big_df.apply(lambda x: x.replace("-", pd.NA))
    big_df = big_df.apply(lambda x: x.replace([None], pd.NA))
    big_df.sort_index(inplace=True)
    big_df.fillna(0, inplace=True)
    big_df = big_df.astype("float")
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    return big_df


# 金十数据中心-经济指标-中国-其他-深圳融资融券报告
def macro_china_market_margin_sz() -> pd.DataFrame:
    """
    深圳融资融券报告, 数据区间从20100331-至今
    https://datacenter.jin10.com/reportType/dc_market_margin_sz
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {"_": t}
    res = requests.get(
        url="https://cdn.jin10.com/data_center/reports/fs_2.json", params=params
    )
    json_data = res.json()
    temp_df = pd.DataFrame(json_data["values"]).T
    temp_df.columns = [
        "融资买入额",
        "融资余额",
        "融券卖出量",
        "融券余量",
        "融券余额",
        "融资融券余额",
    ]
    temp_df.sort_index(inplace=True)
    temp_df.index = pd.to_datetime(temp_df.index)
    temp_df = temp_df.astype("float")
    temp_df.reset_index(inplace=True)
    temp_df.rename(columns={"index": "日期"}, inplace=True)
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    return temp_df


# 金十数据中心-经济指标-中国-其他-上海融资融券报告
def macro_china_market_margin_sh() -> pd.DataFrame:
    """
    上海融资融券报告, 数据区间从 20100331-至今
    https://datacenter.jin10.com/reportType/dc_market_margin_sse
    :return: pandas.DataFrame
    """
    url = "https://cdn.jin10.com/data_center/reports/fs_1.json"
    t = time.time()
    params = {"_": t}
    r = requests.get(url, params=params)
    json_data = r.json()
    temp_df = pd.DataFrame(json_data["values"]).T
    temp_df.reset_index(inplace=True)
    temp_df.columns = [
        "日期",
        "融资买入额",
        "融资余额",
        "融券卖出量",
        "融券余量",
        "融券余额",
        "融资融券余额",
    ]
    temp_df.sort_values(by=["日期"], inplace=True, ignore_index=True)
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["融资买入额"] = pd.to_numeric(temp_df["融资买入额"], errors="coerce")
    temp_df["融资余额"] = pd.to_numeric(temp_df["融资余额"], errors="coerce")
    temp_df["融券卖出量"] = pd.to_numeric(temp_df["融券卖出量"], errors="coerce")
    temp_df["融券余量"] = pd.to_numeric(temp_df["融券余量"], errors="coerce")
    temp_df["融券余额"] = pd.to_numeric(temp_df["融券余额"], errors="coerce")
    temp_df["融资融券余额"] = pd.to_numeric(temp_df["融资融券余额"], errors="coerce")
    return temp_df


# 金十数据中心-经济指标-中国-其他-上海黄金交易所报告
def macro_china_au_report() -> pd.DataFrame:
    """
    上海黄金交易所报告, 数据区间从20100331-至今
    https://datacenter.jin10.com/reportType/dc_sge_report
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {"_": t}
    res = requests.get(
        url="https://cdn.jin10.com/data_center/reports/sge.json", params=params
    )
    json_data = res.json()
    big_df = pd.DataFrame()
    for item in json_data["values"].keys():
        temp_df = pd.DataFrame(json_data["values"][item])
        temp_df["date"] = item
        temp_df.columns = [
            "商品",
            "开盘价",
            "最高价",
            "最低价",
            "收盘价",
            "涨跌",
            "涨跌幅",
            "加权平均价",
            "成交量",
            "成交金额",
            "持仓量",
            "交收方向",
            "交收量",
            "日期",
        ]
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df = big_df[
        [
            "日期",
            "商品",
            "开盘价",
            "最高价",
            "最低价",
            "收盘价",
            "涨跌",
            "涨跌幅",
            "加权平均价",
            "成交量",
            "成交金额",
            "持仓量",
            "交收方向",
            "交收量",
        ]
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df.sort_values(["日期"], inplace=True, ignore_index=True)
    big_df["持仓量"] = pd.to_numeric(big_df["持仓量"], errors="coerce")
    big_df["交收量"] = pd.to_numeric(big_df["交收量"], errors="coerce")
    return big_df


# 中国-利率-贷款报价利率
def macro_china_lpr() -> pd.DataFrame:
    """
    LPR品种详细数据
    https://data.eastmoney.com/cjsj/globalRateLPR.html
    :return: LPR品种详细数据
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)

    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPTA_WEB_RATE",
        "columns": "ALL",
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
        "token": "894050c76af8597a853f5b408b759f5d",
        "pageNumber": "1",
        "pageSize": "500",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df["TRADE_DATE"] = pd.to_datetime(big_df["TRADE_DATE"], errors="coerce").dt.date
    big_df["LPR1Y"] = pd.to_numeric(big_df["LPR1Y"], errors="coerce")
    big_df["LPR5Y"] = pd.to_numeric(big_df["LPR5Y"], errors="coerce")
    big_df["RATE_1"] = pd.to_numeric(big_df["RATE_1"], errors="coerce")
    big_df["RATE_2"] = pd.to_numeric(big_df["RATE_2"], errors="coerce")
    big_df.sort_values(by=["TRADE_DATE"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


# 中国-新房价指数
def macro_china_new_house_price(
    city_first: str = "北京", city_second: str = "上海"
) -> pd.DataFrame:
    """
    中国-新房价指数
    https://data.eastmoney.com/cjsj/newhouse.html
    :param city_first: 城市; 城市列表见目标网站
    :type city_first: str
    :param city_second: 城市; 城市列表见目标网站
    :type city_second: str
    :return: 新房价指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMY_HOUSE_PRICE",
        "columns": "REPORT_DATE,CITY,FIRST_COMHOUSE_SAME,FIRST_COMHOUSE_SEQUENTIAL,FIRST_COMHOUSE_BASE,"
        "SECOND_HOUSE_SAME,SECOND_HOUSE_SEQUENTIAL,SECOND_HOUSE_BASE,REPORT_DAY",
        "filter": f'(CITY in ("{city_first}","{city_second}"))',
        "pageNumber": "1",
        "pageSize": "500",
        "sortColumns": "REPORT_DATE,CITY",
        "sortTypes": "-1,-1",
        "source": "WEB",
        "client": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "日期",
        "城市",
        "新建商品住宅价格指数-同比",
        "新建商品住宅价格指数-环比",
        "新建商品住宅价格指数-定基",
        "二手住宅价格指数-同比",
        "二手住宅价格指数-环比",
        "二手住宅价格指数-定基",
        "-",
    ]
    temp_df = temp_df[
        [
            "日期",
            "城市",
            "新建商品住宅价格指数-同比",
            "新建商品住宅价格指数-环比",
            "新建商品住宅价格指数-定基",
            "二手住宅价格指数-同比",
            "二手住宅价格指数-环比",
            "二手住宅价格指数-定基",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["新建商品住宅价格指数-同比"] = pd.to_numeric(
        temp_df["新建商品住宅价格指数-同比"], errors="coerce"
    )
    temp_df["新建商品住宅价格指数-环比"] = pd.to_numeric(
        temp_df["新建商品住宅价格指数-环比"], errors="coerce"
    )
    temp_df["新建商品住宅价格指数-定基"] = pd.to_numeric(
        temp_df["新建商品住宅价格指数-定基"], errors="coerce"
    )
    temp_df["二手住宅价格指数-环比"] = pd.to_numeric(
        temp_df["二手住宅价格指数-环比"], errors="coerce"
    )
    temp_df["二手住宅价格指数-同比"] = pd.to_numeric(
        temp_df["二手住宅价格指数-同比"], errors="coerce"
    )
    temp_df["二手住宅价格指数-定基"] = pd.to_numeric(
        temp_df["二手住宅价格指数-定基"], errors="coerce"
    )
    temp_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return temp_df


# 中国-企业景气及企业家信心指数
def macro_china_enterprise_boom_index() -> pd.DataFrame:
    """
    https://data.eastmoney.com/cjsj/qyjqzs.html
    中国-企业景气及企业家信心指数
    :return: 企业景气及企业家信心指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,BOOM_INDEX,FAITH_INDEX,BOOM_INDEX_SAME,BOOM_INDEX_SEQUENTIAL,"
        "FAITH_INDEX_SAME,FAITH_INDEX_SEQUENTIAL",
        "pageNumber": "1",
        "pageSize": "500",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_BOOM_INDEX",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "季度",
        "企业景气指数-指数",
        "企业家信心指数-指数",
        "企业景气指数-同比",
        "企业景气指数-环比",
        "企业家信心指数-同比",
        "企业家信心指数-环比",
    ]
    temp_df = temp_df[
        [
            "季度",
            "企业景气指数-指数",
            "企业景气指数-同比",
            "企业景气指数-环比",
            "企业家信心指数-指数",
            "企业家信心指数-同比",
            "企业家信心指数-环比",
        ]
    ]
    temp_df["企业景气指数-指数"] = pd.to_numeric(
        temp_df["企业景气指数-指数"], errors="coerce"
    )
    temp_df["企业家信心指数-指数"] = pd.to_numeric(
        temp_df["企业家信心指数-指数"], errors="coerce"
    )
    temp_df["企业景气指数-同比"] = pd.to_numeric(
        temp_df["企业景气指数-同比"], errors="coerce"
    )
    temp_df["企业景气指数-环比"] = pd.to_numeric(
        temp_df["企业景气指数-环比"], errors="coerce"
    )
    temp_df["企业家信心指数-同比"] = pd.to_numeric(
        temp_df["企业家信心指数-同比"], errors="coerce"
    )
    temp_df["企业家信心指数-环比"] = pd.to_numeric(
        temp_df["企业家信心指数-环比"], errors="coerce"
    )
    return temp_df


# 中国-全国税收收入
def macro_china_national_tax_receipts() -> pd.DataFrame:
    """
    中国-全国税收收入
    https://data.eastmoney.com/cjsj/qgsssr.html
    :return: 全国税收收入
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,TAX_INCOME,TAX_INCOME_SAME,TAX_INCOME_SEQUENTIAL",
        "pageNumber": "1",
        "pageSize": "500",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_TAX",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])

    temp_df.columns = ["-", "季度", "税收收入合计", "较上年同期", "季度环比"]
    temp_df = temp_df[["季度", "税收收入合计", "较上年同期", "季度环比"]]

    temp_df["税收收入合计"] = pd.to_numeric(temp_df["税收收入合计"], errors="coerce")
    temp_df["较上年同期"] = pd.to_numeric(temp_df["较上年同期"], errors="coerce")
    temp_df["季度环比"] = pd.to_numeric(temp_df["季度环比"], errors="coerce")
    return temp_df


# 中国-银行理财产品发行数量
def macro_china_bank_financing() -> pd.DataFrame:
    """
    银行理财产品发行数量
    https://data.eastmoney.com/cjsj/hyzs_list_EMI01516267.html
    :return: 银行理财产品发行数量
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "1000",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI01516267")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"]).dt.date
    temp_df["最新值"] = pd.to_numeric(temp_df["最新值"])
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"])
    temp_df["近3月涨跌幅"] = pd.to_numeric(temp_df["近3月涨跌幅"])
    temp_df["近6月涨跌幅"] = pd.to_numeric(temp_df["近6月涨跌幅"])
    temp_df["近1年涨跌幅"] = pd.to_numeric(temp_df["近1年涨跌幅"])
    temp_df["近2年涨跌幅"] = pd.to_numeric(temp_df["近2年涨跌幅"])
    temp_df["近3年涨跌幅"] = pd.to_numeric(temp_df["近3年涨跌幅"])
    temp_df.sort_values(["日期"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


def macro_china_insurance_income() -> pd.DataFrame:
    """
    原保险保费收入
    https://data.eastmoney.com/cjsj/hyzs_list_EMM00088870.html
    :return: 原保险保费收入
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "1000",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMM00088870")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"]).dt.date
    temp_df["最新值"] = pd.to_numeric(temp_df["最新值"])
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"])
    temp_df["近3月涨跌幅"] = pd.to_numeric(temp_df["近3月涨跌幅"])
    temp_df["近6月涨跌幅"] = pd.to_numeric(temp_df["近6月涨跌幅"])
    temp_df["近1年涨跌幅"] = pd.to_numeric(temp_df["近1年涨跌幅"])
    temp_df["近2年涨跌幅"] = pd.to_numeric(temp_df["近2年涨跌幅"])
    temp_df["近3年涨跌幅"] = pd.to_numeric(temp_df["近3年涨跌幅"])
    temp_df.sort_values(["日期"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


def macro_china_mobile_number() -> pd.DataFrame:
    """
    手机出货量
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00225823.html
    :return: 手机出货量
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "1000",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00225823")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.drop_duplicates(inplace=True)
    temp_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"]).dt.date
    temp_df["最新值"] = pd.to_numeric(temp_df["最新值"])
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"])
    temp_df["近3月涨跌幅"] = pd.to_numeric(temp_df["近3月涨跌幅"])
    temp_df["近6月涨跌幅"] = pd.to_numeric(temp_df["近6月涨跌幅"])
    temp_df["近1年涨跌幅"] = pd.to_numeric(temp_df["近1年涨跌幅"])
    temp_df["近2年涨跌幅"] = pd.to_numeric(temp_df["近2年涨跌幅"])
    temp_df["近3年涨跌幅"] = pd.to_numeric(temp_df["近3年涨跌幅"])
    temp_df.sort_values(["日期"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


def macro_china_vegetable_basket() -> pd.DataFrame:
    """
    菜篮子产品批发价格指数
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00009275.html
    :return: 菜篮子产品批发价格指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00009275")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"])
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"])
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"])
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"])
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"])
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_china_agricultural_product() -> pd.DataFrame:
    """
    农产品批发价格总指数
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00009274.html
    :return: 农产品批发价格总指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00009274")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"])
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"])
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"])
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"])
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"])
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_china_agricultural_index() -> pd.DataFrame:
    """
    农副指数
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00662543.html
    :return: 农副指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00662543")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"])
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"])
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"])
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"])
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"])
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_china_energy_index() -> pd.DataFrame:
    """
    能源指数
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00662539.html
    :return: 能源指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00662539")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"])
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"])
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"])
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"])
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"])
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_china_commodity_price_index() -> pd.DataFrame:
    """
    大宗商品价格
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00662535.html
    :return: 大宗商品价格
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00662535")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"])
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"])
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"])
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"])
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"])
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_global_sox_index() -> pd.DataFrame:
    """
    费城半导体指数
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00055562.html
    :return: 费城半导体指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00055562")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"])
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"])
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"])
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"])
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"])
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_china_yw_electronic_index() -> pd.DataFrame:
    """
    义乌小商品指数-电子元器件
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00055551.html
    :return: 义乌小商品指数-电子元器件
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00055551")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"])
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"])
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"])
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"])
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"])
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_china_construction_index() -> pd.DataFrame:
    """
    建材指数
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00662541.html
    :return: 建材指数
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,"
        "CHANGERATE_1Y,CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00662541")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"], errors="coerce")
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"], errors="coerce")
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"], errors="coerce")
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"], errors="coerce")
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"], errors="coerce")
    big_df.sort_values(by=["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_china_construction_price_index() -> pd.DataFrame:
    """
    建材价格指数
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00237146.html
    :return: 建材价格指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00237146")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"])
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"])
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"])
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"])
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"])
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_china_lpi_index() -> pd.DataFrame:
    """
    物流景气指数
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00352262.html
    :return: 物流景气指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00352262")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"])
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"])
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"])
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"])
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"])
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_china_bdti_index() -> pd.DataFrame:
    """
    原油运输指数
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00107668.html
    :return: 原油运输指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00107668")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"])
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"])
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"])
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"])
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"])
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_china_bsi_index() -> pd.DataFrame:
    """
    超灵便型船运价指数
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00107667.html
    :return: 超灵便型船运价指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMI00107667")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"])
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"])
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"])
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"])
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"])
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"])
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"])
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def _em_macro_1(em_id) -> pd.DataFrame:
    """
    东财宏观数据的一种通用函数
    :return: 处理后的数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    ind_id = '"' + em_id + '"'
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,"
        "CHANGERATE_6M,CHANGERATE_1Y,CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": "(INDICATOR_ID=" + ind_id + ")",
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.drop_duplicates(inplace=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"], errors="coerce")
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"], errors="coerce")
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"], errors="coerce")
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"], errors="coerce")
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"], errors="coerce")
    big_df.sort_values(by=["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_shipping_bci() -> pd.DataFrame:
    """
    海岬型运费指数(BCI)
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00107666.html
    :return: 海岬型运费指数
    :rtype: pandas.DataFrame
    """
    ts = _em_macro_1("EMI00107666")
    return ts


def macro_shipping_bdi() -> pd.DataFrame:
    """
    波罗的海干散货指数(BDI)
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00107664.html
    :return: 波罗的海干散货指数
    :rtype: pandas.DataFrame
    """
    ts = _em_macro_1("EMI00107664")
    return ts


def macro_shipping_bpi() -> pd.DataFrame:
    """
    巴拿马型运费指数(BPI)
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00107665.html
    :return: 巴拿马型运费指数
    :rtype: pandas.DataFrame
    """
    ts = _em_macro_1("EMI00107665")
    return ts


def macro_shipping_bcti() -> pd.DataFrame:
    """
    成品油运输指数（BCTI）
    https://data.eastmoney.com/cjsj/hyzs_list_EMI00107669.html
    :return: 成品油运输指数
    :rtype: pandas.DataFrame
    """
    ts = _em_macro_1("EMI00107669")
    return ts


def macro_china_new_financial_credit() -> pd.DataFrame:
    """
    中国-新增信贷数据
    https://data.eastmoney.com/cjsj/xzxd.html
    :return: 新增信贷数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,RMB_LOAN,RMB_LOAN_SAME,RMB_LOAN_SEQUENTIAL,"
        "RMB_LOAN_ACCUMULATE,LOAN_ACCUMULATE_SAME",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_RMB_LOAN",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])

    temp_df.columns = [
        "-",
        "月份",
        "当月",
        "当月-同比增长",
        "当月-环比增长",
        "累计",
        "累计-同比增长",
    ]
    temp_df = temp_df[
        ["月份", "当月", "当月-同比增长", "当月-环比增长", "累计", "累计-同比增长"]
    ]

    temp_df["当月"] = pd.to_numeric(temp_df["当月"], errors="coerce")
    temp_df["当月-同比增长"] = pd.to_numeric(temp_df["当月-同比增长"], errors="coerce")
    temp_df["当月-环比增长"] = pd.to_numeric(temp_df["当月-环比增长"], errors="coerce")
    temp_df["累计"] = pd.to_numeric(temp_df["累计"], errors="coerce")
    temp_df["累计-同比增长"] = pd.to_numeric(temp_df["累计-同比增长"], errors="coerce")

    return temp_df


def macro_china_fx_gold() -> pd.DataFrame:
    """
    东方财富-外汇和黄金储备
    https://data.eastmoney.com/cjsj/hjwh.html
    :return: 外汇和黄金储备
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.138 Safari/537.36",
    }
    params = {
        "columns": "REPORT_DATE,TIME,GOLD_RESERVES,GOLD_RESERVES_SAME,"
        "GOLD_RESERVES_SEQUENTIAL,FOREX,FOREX_SAME,FOREX_SEQUENTIAL",
        "pageNumber": "1",
        "pageSize": "1000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_GOLD_CURRENCY",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "月份",
        "黄金储备-数值",
        "黄金储备-同比",
        "黄金储备-环比",
        "国家外汇储备-数值",
        "国家外汇储备-同比",
        "国家外汇储备-环比",
    ]
    temp_df = temp_df[
        [
            "月份",
            "黄金储备-数值",
            "黄金储备-同比",
            "黄金储备-环比",
            "国家外汇储备-数值",
            "国家外汇储备-同比",
            "国家外汇储备-环比",
        ]
    ]
    temp_df["国家外汇储备-数值"] = pd.to_numeric(
        temp_df["国家外汇储备-数值"], errors="coerce"
    )
    temp_df["国家外汇储备-同比"] = pd.to_numeric(
        temp_df["国家外汇储备-同比"], errors="coerce"
    )
    temp_df["国家外汇储备-环比"] = pd.to_numeric(
        temp_df["国家外汇储备-环比"], errors="coerce"
    )
    temp_df["黄金储备-数值"] = pd.to_numeric(temp_df["黄金储备-数值"], errors="coerce")
    temp_df["黄金储备-同比"] = pd.to_numeric(temp_df["黄金储备-同比"], errors="coerce")
    temp_df["黄金储备-环比"] = pd.to_numeric(temp_df["黄金储备-环比"], errors="coerce")
    temp_df.sort_values(by=["月份"], inplace=True, ignore_index=True)
    return temp_df


def macro_china_stock_market_cap() -> pd.DataFrame:
    """
    东方财富-全国股票交易统计表
    https://data.eastmoney.com/cjsj/gpjytj.html
    :return: 全国股票交易统计表
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.138 Safari/537.36",
    }
    params = {
        "reportName": "RPT_ECONOMY_STOCK_STATISTICS",
        "columns": "REPORT_DATE,TIME,TOTAL_SHARES_SH,TOTAL_MARKE_SH,DEAL_AMOUNT_SH,VOLUME_SH,HIGH_INDEX_SH,"
        "LOW_INDEX_SH,TOTAL_SZARES_SZ,TOTAL_MARKE_SZ,DEAL_AMOUNT_SZ,VOLUME_SZ,HIGH_INDEX_SZ,LOW_INDEX_SZ",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageNumber": "1",
        "pageSize": "1000",
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "数据日期",
        "发行总股本-上海",
        "市价总值-上海",
        "成交金额-上海",
        "成交量-上海",
        "A股最高综合股价指数-上海",
        "A股最低综合股价指数-上海",
        "发行总股本-深圳",
        "市价总值-深圳",
        "成交金额-深圳",
        "成交量-深圳",
        "A股最高综合股价指数-深圳",
        "A股最低综合股价指数-深圳",
    ]
    temp_df = temp_df[
        [
            "数据日期",
            "发行总股本-上海",
            "发行总股本-深圳",
            "市价总值-上海",
            "市价总值-深圳",
            "成交金额-上海",
            "成交金额-深圳",
            "成交量-上海",
            "成交量-深圳",
            "A股最高综合股价指数-上海",
            "A股最高综合股价指数-深圳",
            "A股最低综合股价指数-上海",
            "A股最低综合股价指数-深圳",
        ]
    ]
    temp_df["发行总股本-上海"] = pd.to_numeric(
        temp_df["发行总股本-上海"], errors="coerce"
    )
    temp_df["发行总股本-深圳"] = pd.to_numeric(
        temp_df["发行总股本-深圳"], errors="coerce"
    )
    temp_df["市价总值-上海"] = pd.to_numeric(temp_df["市价总值-上海"], errors="coerce")
    temp_df["市价总值-深圳"] = pd.to_numeric(temp_df["市价总值-深圳"], errors="coerce")
    temp_df["成交金额-上海"] = pd.to_numeric(temp_df["成交金额-上海"], errors="coerce")
    temp_df["成交金额-深圳"] = pd.to_numeric(temp_df["成交金额-深圳"], errors="coerce")
    temp_df["成交量-上海"] = pd.to_numeric(temp_df["成交量-上海"], errors="coerce")
    temp_df["成交量-深圳"] = pd.to_numeric(temp_df["成交量-深圳"], errors="coerce")
    temp_df["A股最高综合股价指数-上海"] = pd.to_numeric(
        temp_df["A股最高综合股价指数-上海"], errors="coerce"
    )
    temp_df["A股最高综合股价指数-深圳"] = pd.to_numeric(
        temp_df["A股最高综合股价指数-深圳"], errors="coerce"
    )
    temp_df["A股最低综合股价指数-上海"] = pd.to_numeric(
        temp_df["A股最低综合股价指数-上海"], errors="coerce"
    )
    temp_df["A股最低综合股价指数-深圳"] = pd.to_numeric(
        temp_df["A股最低综合股价指数-深圳"], errors="coerce"
    )
    return temp_df


def macro_china_money_supply() -> pd.DataFrame:
    """
    东方财富-货币供应量
    https://data.eastmoney.com/cjsj/hbgyl.html
    :return: 货币供应量
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,BASIC_CURRENCY,BASIC_CURRENCY_SAME,BASIC_CURRENCY_SEQUENTIAL,CURRENCY,"
        "CURRENCY_SAME,CURRENCY_SEQUENTIAL,FREE_CASH,FREE_CASH_SAME,FREE_CASH_SEQUENTIAL",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_CURRENCY_SUPPLY",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "月份",
        "货币和准货币(M2)-数量(亿元)",
        "货币和准货币(M2)-同比增长",
        "货币和准货币(M2)-环比增长",
        "货币(M1)-数量(亿元)",
        "货币(M1)-同比增长",
        "货币(M1)-环比增长",
        "流通中的现金(M0)-数量(亿元)",
        "流通中的现金(M0)-同比增长",
        "流通中的现金(M0)-环比增长",
    ]
    temp_df = temp_df[
        [
            "月份",
            "货币和准货币(M2)-数量(亿元)",
            "货币和准货币(M2)-同比增长",
            "货币和准货币(M2)-环比增长",
            "货币(M1)-数量(亿元)",
            "货币(M1)-同比增长",
            "货币(M1)-环比增长",
            "流通中的现金(M0)-数量(亿元)",
            "流通中的现金(M0)-同比增长",
            "流通中的现金(M0)-环比增长",
        ]
    ]

    temp_df["货币和准货币(M2)-数量(亿元)"] = pd.to_numeric(
        temp_df["货币和准货币(M2)-数量(亿元)"], errors="coerce"
    )
    temp_df["货币和准货币(M2)-同比增长"] = pd.to_numeric(
        temp_df["货币和准货币(M2)-同比增长"], errors="coerce"
    )
    temp_df["货币和准货币(M2)-环比增长"] = pd.to_numeric(
        temp_df["货币和准货币(M2)-环比增长"], errors="coerce"
    )
    temp_df["货币(M1)-数量(亿元)"] = pd.to_numeric(
        temp_df["货币(M1)-数量(亿元)"], errors="coerce"
    )
    temp_df["货币(M1)-同比增长"] = pd.to_numeric(
        temp_df["货币(M1)-同比增长"], errors="coerce"
    )
    temp_df["货币(M1)-环比增长"] = pd.to_numeric(
        temp_df["货币(M1)-环比增长"], errors="coerce"
    )
    temp_df["流通中的现金(M0)-数量(亿元)"] = pd.to_numeric(
        temp_df["流通中的现金(M0)-数量(亿元)"], errors="coerce"
    )
    temp_df["流通中的现金(M0)-同比增长"] = pd.to_numeric(
        temp_df["流通中的现金(M0)-同比增长"], errors="coerce"
    )
    temp_df["流通中的现金(M0)-环比增长"] = pd.to_numeric(
        temp_df["流通中的现金(M0)-环比增长"], errors="coerce"
    )
    return temp_df


def macro_china_cpi() -> pd.DataFrame:
    """
    东方财富-中国居民消费价格指数
    https://data.eastmoney.com/cjsj/cpi.html
    :return: 东方财富-中国居民消费价格指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,NATIONAL_SAME,NATIONAL_BASE,NATIONAL_SEQUENTIAL,NATIONAL_ACCUMULATE,"
        "CITY_SAME,CITY_BASE,CITY_SEQUENTIAL,CITY_ACCUMULATE,RURAL_SAME,"
        "RURAL_BASE,RURAL_SEQUENTIAL,RURAL_ACCUMULATE",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_CPI",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "月份",
        "全国-同比增长",
        "全国-当月",
        "全国-环比增长",
        "全国-累计",
        "城市-同比增长",
        "城市-当月",
        "城市-环比增长",
        "城市-累计",
        "农村-同比增长",
        "农村-当月",
        "农村-环比增长",
        "农村-累计",
    ]
    temp_df = temp_df[
        [
            "月份",
            "全国-当月",
            "全国-同比增长",
            "全国-环比增长",
            "全国-累计",
            "城市-当月",
            "城市-同比增长",
            "城市-环比增长",
            "城市-累计",
            "农村-当月",
            "农村-同比增长",
            "农村-环比增长",
            "农村-累计",
        ]
    ]
    temp_df["全国-当月"] = pd.to_numeric(temp_df["全国-当月"], errors="coerce")
    temp_df["全国-同比增长"] = pd.to_numeric(temp_df["全国-同比增长"], errors="coerce")
    temp_df["全国-环比增长"] = pd.to_numeric(temp_df["全国-环比增长"], errors="coerce")
    temp_df["全国-累计"] = pd.to_numeric(temp_df["全国-累计"], errors="coerce")
    temp_df["城市-当月"] = pd.to_numeric(temp_df["城市-当月"], errors="coerce")
    temp_df["城市-同比增长"] = pd.to_numeric(temp_df["城市-同比增长"], errors="coerce")
    temp_df["城市-环比增长"] = pd.to_numeric(temp_df["城市-环比增长"], errors="coerce")
    temp_df["城市-累计"] = pd.to_numeric(temp_df["城市-累计"], errors="coerce")
    temp_df["农村-当月"] = pd.to_numeric(temp_df["农村-当月"], errors="coerce")
    temp_df["农村-同比增长"] = pd.to_numeric(temp_df["农村-同比增长"], errors="coerce")
    temp_df["农村-环比增长"] = pd.to_numeric(temp_df["农村-环比增长"], errors="coerce")
    temp_df["农村-累计"] = pd.to_numeric(temp_df["农村-累计"], errors="coerce")

    return temp_df


def macro_china_gdp() -> pd.DataFrame:
    """
    东方财富-中国国内生产总值
    https://data.eastmoney.com/cjsj/gdp.html
    :return: 东方财富中国国内生产总值
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,DOMESTICL_PRODUCT_BASE,FIRST_PRODUCT_BASE,SECOND_PRODUCT_BASE,"
        "THIRD_PRODUCT_BASE,SUM_SAME,FIRST_SAME,SECOND_SAME,THIRD_SAME",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_GDP",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "季度",
        "国内生产总值-绝对值",
        "第一产业-绝对值",
        "第二产业-绝对值",
        "第三产业-绝对值",
        "国内生产总值-同比增长",
        "第一产业-同比增长",
        "第二产业-同比增长",
        "第三产业-同比增长",
    ]
    temp_df = temp_df[
        [
            "季度",
            "国内生产总值-绝对值",
            "国内生产总值-同比增长",
            "第一产业-绝对值",
            "第一产业-同比增长",
            "第二产业-绝对值",
            "第二产业-同比增长",
            "第三产业-绝对值",
            "第三产业-同比增长",
        ]
    ]
    temp_df["国内生产总值-绝对值"] = pd.to_numeric(
        temp_df["国内生产总值-绝对值"], errors="coerce"
    )
    temp_df["国内生产总值-同比增长"] = pd.to_numeric(
        temp_df["国内生产总值-同比增长"], errors="coerce"
    )
    temp_df["第一产业-绝对值"] = pd.to_numeric(
        temp_df["第一产业-绝对值"], errors="coerce"
    )
    temp_df["第一产业-同比增长"] = pd.to_numeric(
        temp_df["第一产业-同比增长"], errors="coerce"
    )
    temp_df["第二产业-绝对值"] = pd.to_numeric(
        temp_df["第二产业-绝对值"], errors="coerce"
    )
    temp_df["第二产业-同比增长"] = pd.to_numeric(
        temp_df["第二产业-同比增长"], errors="coerce"
    )
    temp_df["第三产业-绝对值"] = pd.to_numeric(
        temp_df["第三产业-绝对值"], errors="coerce"
    )
    temp_df["第三产业-同比增长"] = pd.to_numeric(
        temp_df["第三产业-同比增长"], errors="coerce"
    )
    return temp_df


def macro_china_ppi() -> pd.DataFrame:
    """
    东方财富-中国工业品出厂价格指数
    https://data.eastmoney.com/cjsj/ppi.html
    :return: 东方财富中国工业品出厂价格指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,BASE,BASE_SAME,BASE_ACCUMULATE",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_PPI",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "月份",
        "当月",
        "当月同比增长",
        "累计",
    ]
    temp_df = temp_df[
        [
            "月份",
            "当月",
            "当月同比增长",
            "累计",
        ]
    ]
    temp_df["当月"] = pd.to_numeric(temp_df["当月"], errors="coerce")
    temp_df["当月同比增长"] = pd.to_numeric(temp_df["当月同比增长"], errors="coerce")
    temp_df["累计"] = pd.to_numeric(temp_df["累计"], errors="coerce")
    return temp_df


def macro_china_pmi() -> pd.DataFrame:
    """
    东方财富-中国采购经理人指数
    https://data.eastmoney.com/cjsj/pmi.html
    :return: 东方财富中国采购经理人指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,MAKE_INDEX,MAKE_SAME,NMAKE_INDEX,NMAKE_SAME",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_PMI",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "月份",
        "制造业-指数",
        "制造业-同比增长",
        "非制造业-指数",
        "非制造业-同比增长",
    ]
    temp_df = temp_df[
        [
            "月份",
            "制造业-指数",
            "制造业-同比增长",
            "非制造业-指数",
            "非制造业-同比增长",
        ]
    ]
    temp_df["制造业-指数"] = pd.to_numeric(temp_df["制造业-指数"], errors="coerce")
    temp_df["制造业-同比增长"] = pd.to_numeric(
        temp_df["制造业-同比增长"], errors="coerce"
    )
    temp_df["非制造业-指数"] = pd.to_numeric(temp_df["非制造业-指数"], errors="coerce")
    temp_df["非制造业-同比增长"] = pd.to_numeric(
        temp_df["非制造业-同比增长"], errors="coerce"
    )
    return temp_df


def macro_china_gdzctz() -> pd.DataFrame:
    """
    东方财富-中国城镇固定资产投资
    https://data.eastmoney.com/cjsj/gdzctz.html
    :return: 东方财富中国城镇固定资产投资
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,BASE,BASE_SAME,BASE_SEQUENTIAL,BASE_ACCUMULATE",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_ASSET_INVEST",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])

    temp_df.columns = [
        "-",
        "月份",
        "当月",
        "同比增长",
        "环比增长",
        "自年初累计",
    ]
    temp_df = temp_df[
        [
            "月份",
            "当月",
            "同比增长",
            "环比增长",
            "自年初累计",
        ]
    ]
    temp_df["当月"] = pd.to_numeric(temp_df["当月"], errors="coerce")
    temp_df["同比增长"] = pd.to_numeric(temp_df["同比增长"], errors="coerce")
    temp_df["环比增长"] = pd.to_numeric(temp_df["环比增长"], errors="coerce")
    temp_df["自年初累计"] = pd.to_numeric(temp_df["自年初累计"], errors="coerce")
    return temp_df


def macro_china_hgjck() -> pd.DataFrame:
    """
    东方财富-海关进出口增减情况一览表
    https://data.eastmoney.com/cjsj/hgjck.html
    :return: 东方财富-海关进出口增减情况一览表
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,EXIT_BASE,IMPORT_BASE,EXIT_BASE_SAME,IMPORT_BASE_SAME,"
        "EXIT_BASE_SEQUENTIAL,IMPORT_BASE_SEQUENTIAL,EXIT_ACCUMULATE,"
        "IMPORT_ACCUMULATE,EXIT_ACCUMULATE_SAME,IMPORT_ACCUMULATE_SAME",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_CUSTOMS",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.rename(
        columns={
            "REPORT_DATE": "-",
            "TIME": "月份",
            "EXIT_BASE": "当月出口额-金额",
            "IMPORT_BASE": "当月进口额-金额",
            "EXIT_BASE_SAME": "当月出口额-同比增长",
            "IMPORT_BASE_SAME": "当月进口额-同比增长",
            "EXIT_BASE_SEQUENTIAL": "当月出口额-环比增长",
            "IMPORT_BASE_SEQUENTIAL": "当月进口额-环比增长",
            "EXIT_ACCUMULATE": "累计出口额-金额",
            "IMPORT_ACCUMULATE": "累计进口额-金额",
            "EXIT_ACCUMULATE_SAME": "累计出口额-同比增长",
            "IMPORT_ACCUMULATE_SAME": "累计进口额-同比增长",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "月份",
            "当月出口额-金额",
            "当月出口额-同比增长",
            "当月出口额-环比增长",
            "当月进口额-金额",
            "当月进口额-同比增长",
            "当月进口额-环比增长",
            "累计出口额-金额",
            "累计出口额-同比增长",
            "累计进口额-金额",
            "累计进口额-同比增长",
        ]
    ]
    temp_df["当月出口额-金额"] = pd.to_numeric(
        temp_df["当月出口额-金额"], errors="coerce"
    )
    temp_df["当月出口额-同比增长"] = pd.to_numeric(
        temp_df["当月出口额-同比增长"], errors="coerce"
    )
    temp_df["当月出口额-环比增长"] = pd.to_numeric(
        temp_df["当月出口额-环比增长"], errors="coerce"
    )
    temp_df["当月进口额-金额"] = pd.to_numeric(
        temp_df["当月进口额-金额"], errors="coerce"
    )
    temp_df["当月进口额-同比增长"] = pd.to_numeric(
        temp_df["当月进口额-同比增长"], errors="coerce"
    )
    temp_df["当月进口额-环比增长"] = pd.to_numeric(
        temp_df["当月进口额-环比增长"], errors="coerce"
    )
    temp_df["累计出口额-金额"] = pd.to_numeric(
        temp_df["累计出口额-金额"], errors="coerce"
    )
    temp_df["累计出口额-同比增长"] = pd.to_numeric(
        temp_df["累计出口额-同比增长"], errors="coerce"
    )
    temp_df["累计进口额-金额"] = pd.to_numeric(
        temp_df["累计进口额-金额"], errors="coerce"
    )
    temp_df["累计进口额-同比增长"] = pd.to_numeric(
        temp_df["累计进口额-同比增长"], errors="coerce"
    )
    return temp_df


def macro_china_czsr() -> pd.DataFrame:
    """
    东方财富-财政收入
    https://data.eastmoney.com/cjsj/czsr.html
    :return: 东方财富-财政收入
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,BASE,BASE_SAME,BASE_SEQUENTIAL,BASE_ACCUMULATE,ACCUMULATE_SAME",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_INCOME",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])

    temp_df.columns = [
        "-",
        "月份",
        "当月",
        "当月-同比增长",
        "当月-环比增长",
        "累计",
        "累计-同比增长",
    ]
    temp_df = temp_df[
        [
            "月份",
            "当月",
            "当月-同比增长",
            "当月-环比增长",
            "累计",
            "累计-同比增长",
        ]
    ]
    temp_df["当月"] = pd.to_numeric(temp_df["当月"], errors="coerce")
    temp_df["当月-同比增长"] = pd.to_numeric(temp_df["当月-同比增长"], errors="coerce")
    temp_df["当月-环比增长"] = pd.to_numeric(temp_df["当月-环比增长"], errors="coerce")
    temp_df["累计"] = pd.to_numeric(temp_df["累计"], errors="coerce")
    temp_df["累计-同比增长"] = pd.to_numeric(temp_df["累计-同比增长"], errors="coerce")

    return temp_df


def macro_china_whxd() -> pd.DataFrame:
    """
    东方财富-外汇贷款数据
    https://data.eastmoney.com/cjsj/whxd.html
    :return: 东方财富-外汇贷款数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,BASE,BASE_SAME,BASE_SEQUENTIAL,BASE_ACCUMULATE",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_FOREX_LOAN",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])

    temp_df.columns = [
        "-",
        "月份",
        "当月",
        "同比增长",
        "环比增长",
        "累计",
    ]
    temp_df = temp_df[
        [
            "月份",
            "当月",
            "同比增长",
            "环比增长",
            "累计",
        ]
    ]
    temp_df["当月"] = pd.to_numeric(temp_df["当月"], errors="coerce")
    temp_df["同比增长"] = pd.to_numeric(temp_df["同比增长"], errors="coerce")
    temp_df["环比增长"] = pd.to_numeric(temp_df["环比增长"], errors="coerce")
    temp_df["累计"] = pd.to_numeric(temp_df["累计"], errors="coerce")
    return temp_df


def macro_china_wbck() -> pd.DataFrame:
    """
    东方财富-本外币存款
    https://data.eastmoney.com/cjsj/wbck.html
    :return: 东方财富-本外币存款
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,BASE,BASE_SAME,BASE_SEQUENTIAL,BASE_ACCUMULATE",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_FOREX_DEPOSIT",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])

    temp_df.columns = [
        "-",
        "月份",
        "当月",
        "同比增长",
        "环比增长",
        "累计",
    ]
    temp_df = temp_df[
        [
            "月份",
            "当月",
            "同比增长",
            "环比增长",
            "累计",
        ]
    ]
    temp_df["当月"] = pd.to_numeric(temp_df["当月"], errors="coerce")
    temp_df["同比增长"] = pd.to_numeric(temp_df["同比增长"], errors="coerce")
    temp_df["环比增长"] = pd.to_numeric(temp_df["环比增长"], errors="coerce")
    temp_df["累计"] = pd.to_numeric(temp_df["累计"], errors="coerce")

    return temp_df


def macro_china_xfzxx() -> pd.DataFrame:
    """
    东方财富网-经济数据一览-消费者信心指数
    https://data.eastmoney.com/cjsj/xfzxx.html
    :return: 消费者信心指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,CONSUMERS_FAITH_INDEX,FAITH_INDEX_SAME,FAITH_INDEX_SEQUENTIAL,"
        "CONSUMERS_ASTIS_INDEX,ASTIS_INDEX_SAME,ASTIS_INDEX_SEQUENTIAL,CONSUMERS_EXPECT_INDEX,"
        "EXPECT_INDEX_SAME,EXPECT_INDEX_SEQUENTIAL",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_FAITH_INDEX",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])

    temp_df.columns = [
        "-",
        "月份",
        "消费者信心指数-指数值",
        "消费者信心指数-同比增长",
        "消费者信心指数-环比增长",
        "消费者满意指数-指数值",
        "消费者满意指数-同比增长",
        "消费者满意指数-环比增长",
        "消费者预期指数-指数值",
        "消费者预期指数-同比增长",
        "消费者预期指数-环比增长",
    ]
    temp_df = temp_df[
        [
            "月份",
            "消费者信心指数-指数值",
            "消费者信心指数-同比增长",
            "消费者信心指数-环比增长",
            "消费者满意指数-指数值",
            "消费者满意指数-同比增长",
            "消费者满意指数-环比增长",
            "消费者预期指数-指数值",
            "消费者预期指数-同比增长",
            "消费者预期指数-环比增长",
        ]
    ]

    temp_df["消费者信心指数-指数值"] = pd.to_numeric(
        temp_df["消费者信心指数-指数值"], errors="coerce"
    )
    temp_df["消费者信心指数-同比增长"] = pd.to_numeric(
        temp_df["消费者信心指数-同比增长"], errors="coerce"
    )
    temp_df["消费者信心指数-环比增长"] = pd.to_numeric(
        temp_df["消费者信心指数-环比增长"], errors="coerce"
    )
    temp_df["消费者满意指数-指数值"] = pd.to_numeric(
        temp_df["消费者满意指数-指数值"], errors="coerce"
    )
    temp_df["消费者满意指数-同比增长"] = pd.to_numeric(
        temp_df["消费者满意指数-同比增长"], errors="coerce"
    )
    temp_df["消费者满意指数-环比增长"] = pd.to_numeric(
        temp_df["消费者满意指数-环比增长"], errors="coerce"
    )
    temp_df["消费者预期指数-指数值"] = pd.to_numeric(
        temp_df["消费者满意指数-指数值"], errors="coerce"
    )
    temp_df["消费者预期指数-同比增长"] = pd.to_numeric(
        temp_df["消费者预期指数-同比增长"], errors="coerce"
    )
    temp_df["消费者预期指数-环比增长"] = pd.to_numeric(
        temp_df["消费者预期指数-环比增长"], errors="coerce"
    )
    return temp_df


def macro_china_gyzjz() -> pd.DataFrame:
    """
    东方财富网-经济数据-工业增加值增长
    https://data.eastmoney.com/cjsj/gyzjz.html
    :return: 工业增加值增长
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,BASE_SAME,BASE_ACCUMULATE",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_INDUS_GROW",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "发布时间",
        "月份",
        "同比增长",
        "累计增长",
    ]
    temp_df = temp_df[
        [
            "月份",
            "同比增长",
            "累计增长",
            "发布时间",
        ]
    ]
    temp_df["同比增长"] = pd.to_numeric(temp_df["同比增长"], errors="coerce")
    temp_df["累计增长"] = pd.to_numeric(temp_df["累计增长"], errors="coerce")
    temp_df["发布时间"] = pd.to_datetime(temp_df["发布时间"], errors="coerce").dt.date
    temp_df.sort_values(["发布时间"], ignore_index=True, inplace=True)
    return temp_df


def macro_china_reserve_requirement_ratio() -> pd.DataFrame:
    """
    存款准备金率
    https://data.eastmoney.com/cjsj/ckzbj.html
    :return: 存款准备金率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,PUBLISH_DATE,TRADE_DATE,INTEREST_RATE_BB,INTEREST_RATE_BA,CHANGE_RATE_B,"
        "INTEREST_RATE_SB,INTEREST_RATE_SA,CHANGE_RATE_S,NEXT_SH_RATE,NEXT_SZ_RATE,REMARK",
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "PUBLISH_DATE,TRADE_DATE",
        "sortTypes": "-1,-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_DEPOSIT_RESERVE",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "公布时间",
        "生效时间",
        "大型金融机构-调整前",
        "大型金融机构-调整后",
        "大型金融机构-调整幅度",
        "中小金融机构-调整前",
        "中小金融机构-调整后",
        "中小金融机构-调整幅度",
        "消息公布次日指数涨跌-上证",
        "消息公布次日指数涨跌-深证",
        "备注",
    ]
    temp_df = temp_df[
        [
            "公布时间",
            "生效时间",
            "大型金融机构-调整前",
            "大型金融机构-调整后",
            "大型金融机构-调整幅度",
            "中小金融机构-调整前",
            "中小金融机构-调整后",
            "中小金融机构-调整幅度",
            "消息公布次日指数涨跌-上证",
            "消息公布次日指数涨跌-深证",
            "备注",
        ]
    ]
    temp_df["大型金融机构-调整前"] = pd.to_numeric(
        temp_df["大型金融机构-调整前"], errors="coerce"
    )
    temp_df["大型金融机构-调整后"] = pd.to_numeric(
        temp_df["大型金融机构-调整后"], errors="coerce"
    )
    temp_df["大型金融机构-调整幅度"] = pd.to_numeric(
        temp_df["大型金融机构-调整幅度"], errors="coerce"
    )
    temp_df["大型金融机构-调整前"] = pd.to_numeric(
        temp_df["大型金融机构-调整前"], errors="coerce"
    )
    temp_df["大型金融机构-调整后"] = pd.to_numeric(
        temp_df["大型金融机构-调整后"], errors="coerce"
    )
    temp_df["大型金融机构-调整幅度"] = pd.to_numeric(
        temp_df["大型金融机构-调整幅度"], errors="coerce"
    )
    temp_df["消息公布次日指数涨跌-上证"] = pd.to_numeric(
        temp_df["消息公布次日指数涨跌-上证"], errors="coerce"
    )
    temp_df["消息公布次日指数涨跌-深证"] = pd.to_numeric(
        temp_df["消息公布次日指数涨跌-深证"], errors="coerce"
    )
    temp_df["消息公布次日指数涨跌-深证"] = pd.to_numeric(
        temp_df["消息公布次日指数涨跌-深证"], errors="coerce"
    )
    return temp_df


def macro_china_consumer_goods_retail() -> pd.DataFrame:
    """
    东方财富-经济数据-社会消费品零售总额
    https://data.eastmoney.com/cjsj/xfp.html
    :return: 社会消费品零售总额
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.138 Safari/537.36",
    }
    params = {
        "columns": "REPORT_DATE,TIME,RETAIL_TOTAL,RETAIL_TOTAL_SAME,RETAIL_TOTAL_SEQUENTIAL,"
        "RETAIL_TOTAL_ACCUMULATE,RETAIL_ACCUMULATE_SAME",
        "pageNumber": "1",
        "pageSize": "1000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_TOTAL_RETAIL",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "-",
        "月份",
        "当月",
        "同比增长",
        "环比增长",
        "累计",
        "累计-同比增长",
    ]
    temp_df = temp_df[
        [
            "月份",
            "当月",
            "同比增长",
            "环比增长",
            "累计",
            "累计-同比增长",
        ]
    ]
    temp_df["当月"] = pd.to_numeric(temp_df["当月"], errors="coerce")
    temp_df["同比增长"] = pd.to_numeric(temp_df["同比增长"], errors="coerce")
    temp_df["环比增长"] = pd.to_numeric(temp_df["环比增长"], errors="coerce")
    temp_df["累计"] = pd.to_numeric(temp_df["累计"], errors="coerce")
    temp_df["累计-同比增长"] = pd.to_numeric(temp_df["累计-同比增长"], errors="coerce")
    return temp_df


def macro_china_society_electricity() -> pd.DataFrame:
    """
    新浪财经-中国宏观经济数据-全社会用电分类情况表
    https://finance.sina.com.cn/mac/#industry-6-0-31-1
    :return: 全社会用电分类情况表
    :rtype: pandas.DataFrame
    """
    url = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601557771972/MacPage_Service.get_pagedata"
    params = {
        "cate": "industry",
        "event": "6",
        "from": "0",
        "num": "31",
        "condition": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"])
    for i in range(1, page_num):
        params.update({"from": i * 31})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        temp_df = pd.DataFrame(data_json["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)

    big_df.columns = [
        "统计时间",
        "全社会用电量",
        "全社会用电量同比",
        "各行业用电量合计",
        "各行业用电量合计同比",
        "第一产业用电量",
        "第一产业用电量同比",
        "第二产业用电量",
        "第二产业用电量同比",
        "第三产业用电量",
        "第三产业用电量同比",
        "城乡居民生活用电量合计",
        "城乡居民生活用电量合计同比",
        "城镇居民用电量",
        "城镇居民用电量同比",
        "乡村居民用电量",
        "乡村居民用电量同比",
    ]
    for item in big_df.columns[1:]:
        big_df[item] = pd.to_numeric(big_df[item], errors="coerce")
    big_df.sort_values(["统计时间"], inplace=True, ignore_index=True)
    return big_df


def macro_china_society_traffic_volume() -> pd.DataFrame:
    """
    新浪财经-中国宏观经济数据-全社会客货运输量
    https://finance.sina.com.cn/mac/#industry-10-0-31-1
    :return: 全社会客货运输量
    :rtype: pandas.DataFrame
    """
    url = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601559094538/MacPage_Service.get_pagedata"
    params = {
        "cate": "industry",
        "event": "10",
        "from": "0",
        "num": "31",
        "condition": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"]["非累计"])
    tqdm = get_tqdm()
    for i in tqdm(range(1, page_num), leave=False):
        params.update({"from": i * 31})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        temp_df = pd.DataFrame(data_json["data"]["非累计"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.columns = [item[1] for item in data_json["config"]["all"]]
    big_df["货运量"] = pd.to_numeric(big_df["货运量"], errors="coerce")
    big_df["货运量同比增长"] = pd.to_numeric(big_df["货运量同比增长"], errors="coerce")
    big_df["货物周转量"] = pd.to_numeric(big_df["货物周转量"], errors="coerce")
    big_df["公里货物周转量同比增长"] = pd.to_numeric(
        big_df["公里货物周转量同比增长"], errors="coerce"
    )
    big_df["客运量"] = pd.to_numeric(big_df["客运量"], errors="coerce")
    big_df["客运量同比增长"] = pd.to_numeric(big_df["客运量同比增长"], errors="coerce")
    big_df["旅客周转量"] = pd.to_numeric(big_df["旅客周转量"], errors="coerce")
    big_df["公里旅客周转量同比增长"] = pd.to_numeric(
        big_df["公里旅客周转量同比增长"], errors="coerce"
    )
    big_df["沿海主要港口货物吞吐量"] = pd.to_numeric(
        big_df["沿海主要港口货物吞吐量"], errors="coerce"
    )
    big_df["沿海主要港口货物吞吐量同比增长"] = pd.to_numeric(
        big_df["沿海主要港口货物吞吐量同比增长"], errors="coerce"
    )
    big_df["其中:外贸货物吞吐量"] = pd.to_numeric(
        big_df["其中:外贸货物吞吐量"], errors="coerce"
    )
    big_df["其中:外贸货物吞吐量同比增长"] = pd.to_numeric(
        big_df["其中:外贸货物吞吐量同比增长"], errors="coerce"
    )
    big_df["民航总周转量"] = pd.to_numeric(big_df["民航总周转量"], errors="coerce")
    big_df["公里民航总周转"] = pd.to_numeric(big_df["公里民航总周转"], errors="coerce")
    return big_df


def macro_china_postal_telecommunicational() -> pd.DataFrame:
    """
    新浪财经-中国宏观经济数据-邮电业务基本情况
    https://finance.sina.com.cn/mac/#industry-11-0-31-1
    :return: 邮电业务基本情况
    :rtype: pandas.DataFrame
    """
    url = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601624495046/MacPage_Service.get_pagedata"
    params = {
        "cate": "industry",
        "event": "11",
        "from": "0",
        "num": "31",
        "condition": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"]["非累计"])
    tqdm = get_tqdm()
    for i in tqdm(range(1, page_num), leave=False):
        params.update({"from": i * 31})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        temp_df = pd.DataFrame(data_json["data"]["非累计"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [item[1] for item in data_json["config"]["all"]]
    for item in big_df.columns[1:]:
        big_df[item] = pd.to_numeric(big_df[item], errors="coerce")
    return big_df


def macro_china_international_tourism_fx() -> pd.DataFrame:
    """
    新浪财经-中国宏观经济数据-国际旅游外汇收入构成
    https://finance.sina.com.cn/mac/#industry-15-0-31-3
    :return: 国际旅游外汇收入构成
    :rtype: pandas.DataFrame
    """
    url = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601651495761/MacPage_Service.get_pagedata"
    params = {
        "cate": "industry",
        "event": "15",
        "from": "0",
        "num": "31",
        "condition": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"])
    tqdm = get_tqdm()
    for i in tqdm(range(1, page_num)):
        params.update({"from": i * 31})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        temp_df = pd.DataFrame(data_json["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.columns = [item[1] for item in data_json["config"]["all"]]
    big_df["数量"] = pd.to_numeric(big_df["数量"], errors="coerce")
    big_df["比重"] = pd.to_numeric(big_df["比重"], errors="coerce")
    return big_df


def macro_china_passenger_load_factor() -> pd.DataFrame:
    """
    新浪财经-中国宏观经济数据-民航客座率及载运率
    https://finance.sina.com.cn/mac/#industry-20-0-31-1
    :return: 民航客座率及载运率
    :rtype: pandas.DataFrame
    """
    url = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601651495761/MacPage_Service.get_pagedata"
    params = {
        "cate": "industry",
        "event": "20",
        "from": "0",
        "num": "31",
        "condition": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"])
    tqdm = get_tqdm()
    for i in tqdm(range(1, page_num)):
        params.update({"from": i * 31})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        temp_df = pd.DataFrame(data_json["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [item[1] for item in data_json["config"]["all"]]
    big_df["客座率"] = pd.to_numeric(big_df["客座率"], errors="coerce")
    big_df["载运率"] = pd.to_numeric(big_df["载运率"], errors="coerce")
    return big_df


def _macro_china_freight_index() -> pd.DataFrame:
    """
    新浪财经-中国宏观经济数据-航贸运价指数
    https://finance.sina.com.cn/mac/#industry-22-0-31-2
    :return: 航贸运价指数
    :rtype: pandas.DataFrame
    """
    url = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601651495761/MacPage_Service.get_pagedata"
    params = {
        "cate": "industry",
        "event": "22",
        "from": "0",
        "num": "31",
        "condition": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"])
    tqdm = get_tqdm()
    for i in tqdm(range(1, page_num)):
        params.update({"from": i * 31})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        temp_df = pd.DataFrame(data_json["data"])
        big_df = big_df.append(temp_df, ignore_index=True)
    big_df.columns = [item[1] for item in data_json["config"]["all"]]
    return big_df


def macro_china_freight_index() -> pd.DataFrame:
    """
    新浪财经-中国宏观经济数据-航贸运价指数
    https://finance.sina.com.cn/mac/#industry-22-0-31-2
    :return: 航贸运价指数
    :rtype: pandas.DataFrame
    """
    url = "http://quotes.sina.cn/mac/view/vMacExcle.php"
    params = {
        "cate": "industry",
        "event": "22",
        "from": "0",
        "num": 5000,
        "condition": "",
    }
    r = requests.get(url, params=params)
    columns_list = r.content.decode("gbk").split("\n")[2].split(", ")
    columns_list = [item.strip() for item in columns_list]
    content_list = r.content.decode("gbk").split("\n")[3:]
    big_df = (
        pd.DataFrame([item.split(", ") for item in content_list], columns=columns_list)
        .dropna(axis=1, how="all")
        .dropna(axis=0)
        .iloc[:, :-1]
    )
    big_df["波罗的海好望角型船运价指数BCI"] = pd.to_numeric(
        big_df["波罗的海好望角型船运价指数BCI"]
    )
    big_df["灵便型船综合运价指数BHMI"] = pd.to_numeric(
        big_df["灵便型船综合运价指数BHMI"]
    )
    big_df["波罗的海超级大灵便型船BSI指数"] = pd.to_numeric(
        big_df["波罗的海超级大灵便型船BSI指数"]
    )
    big_df["波罗的海综合运价指数BDI"] = pd.to_numeric(big_df["波罗的海综合运价指数BDI"])
    big_df["HRCI国际集装箱租船指数"] = pd.to_numeric(big_df["HRCI国际集装箱租船指数"])
    big_df["油轮运价指数成品油运价指数BCTI"] = pd.to_numeric(
        big_df["油轮运价指数成品油运价指数BCTI"]
    )
    big_df["油轮运价指数原油运价指数BDTI"] = pd.to_numeric(
        big_df["油轮运价指数原油运价指数BDTI"]
    )
    return big_df


def macro_china_central_bank_balance() -> pd.DataFrame:
    """
    新浪财经-中国宏观经济数据-央行货币当局资产负债
    https://finance.sina.com.cn/mac/#fininfo-8-0-31-2
    :return: 央行货币当局资产负债
    :rtype: pandas.DataFrame
    """
    url = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601651495761/MacPage_Service.get_pagedata"
    params = {
        "cate": "fininfo",
        "event": "8",
        "from": "0",
        "num": "31",
        "condition": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"])
    tqdm = get_tqdm()
    for i in tqdm(range(1, page_num)):
        params.update({"from": i * 31})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        temp_df = pd.DataFrame(data_json["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.columns = [item[1] for item in data_json["config"]["all"]]
    for item in big_df.columns[1:]:
        big_df[item] = pd.to_numeric(big_df[item], errors="coerce")
    return big_df


def macro_china_insurance() -> pd.DataFrame:
    """
    新浪财经-中国宏观经济数据-保险业经营情况
    https://finance.sina.com.cn/mac/#fininfo-19-0-31-3
    :return: 保险业经营情况
    :rtype: pandas.DataFrame
    """
    url = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601651495761/MacPage_Service.get_pagedata"
    params = {
        "cate": "fininfo",
        "event": "19",
        "from": "0",
        "num": "31",
        "condition": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"])
    tqdm = get_tqdm()
    for i in tqdm(range(1, page_num)):
        params.update({"from": i * 31})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        temp_df = pd.DataFrame(data_json["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.columns = [item[1] for item in data_json["config"]["all"]]
    for item in big_df.columns[2:]:
        big_df[item] = pd.to_numeric(big_df[item], errors="coerce")
    return big_df


def macro_china_supply_of_money() -> pd.DataFrame:
    """
    新浪财经-中国宏观经济数据-货币供应量
    https://finance.sina.com.cn/mac/#fininfo-1-0-31-1
    :return: 货币供应量
    :rtype: pandas.DataFrame
    """
    url = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601651495761/MacPage_Service.get_pagedata"
    params = {
        "cate": "fininfo",
        "event": "1",
        "from": "0",
        "num": "31",
        "condition": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"])
    tqdm = get_tqdm()
    for i in tqdm(range(1, page_num)):
        params.update({"from": i * 31})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        temp_df = pd.DataFrame(data_json["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [item[1] for item in data_json["config"]["all"]]
    for item in big_df.columns[1:]:
        big_df[item] = pd.to_numeric(big_df[item], errors="coerce")
    return big_df


def macro_china_foreign_exchange_gold() -> pd.DataFrame:
    """
    央行黄金和外汇储备
    https://finance.sina.com.cn/mac/#fininfo-5-0-31-2
    :return: 央行黄金和外汇储备
    :rtype: pandas.DataFrame
    """
    url = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601651495761/MacPage_Service.get_pagedata"
    params = {
        "cate": "fininfo",
        "event": "5",
        "from": "0",
        "num": "31",
        "condition": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"])
    tqdm = get_tqdm()
    for i in tqdm(range(1, page_num), leave=False):
        params.update({"from": i * 31})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        temp_df = pd.DataFrame(data_json["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [item[1] for item in data_json["config"]["all"]]
    big_df.sort_values(by=["统计时间"], ignore_index=True, inplace=True)
    big_df["黄金储备"] = pd.to_numeric(big_df["黄金储备"], errors="coerce")
    big_df["国家外汇储备"] = pd.to_numeric(big_df["国家外汇储备"], errors="coerce")
    return big_df


def macro_china_retail_price_index() -> pd.DataFrame:
    """
    商品零售价格指数
    https://finance.sina.com.cn/mac/#price-12-0-31-1
    :return: 商品零售价格指数
    :rtype: pandas.DataFrame
    """
    url = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601651495761/MacPage_Service.get_pagedata"
    params = {
        "cate": "price",
        "event": "12",
        "from": "0",
        "num": "31",
        "condition": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"])
    tqdm = get_tqdm()
    for i in tqdm(range(1, page_num), leave=False):
        params.update({"from": i * 31})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        temp_df = pd.DataFrame(data_json["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [item[1] for item in data_json["config"]["all"]]
    big_df.sort_values(by=["统计月份"], ignore_index=True, inplace=True)
    big_df["零售商品价格指数"] = pd.to_numeric(
        big_df["零售商品价格指数"], errors="coerce"
    )
    return big_df


def macro_china_real_estate() -> pd.DataFrame:
    """
    国房景气指数
    https://data.eastmoney.com/cjsj/hyzs_list_EMM00121987.html
    :return: 国房景气指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.138 Safari/537.36",
    }
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "1000",
        "pageNumber": "1",
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE,CHANGE_RATE,CHANGERATE_3M,CHANGERATE_6M,CHANGERATE_1Y,"
        "CHANGERATE_2Y,CHANGERATE_3Y",
        "filter": '(INDICATOR_ID="EMM00121987")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "日期",
        "最新值",
        "涨跌幅",
        "近3月涨跌幅",
        "近6月涨跌幅",
        "近1年涨跌幅",
        "近2年涨跌幅",
        "近3年涨跌幅",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["最新值"] = pd.to_numeric(big_df["最新值"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["近3月涨跌幅"] = pd.to_numeric(big_df["近3月涨跌幅"], errors="coerce")
    big_df["近6月涨跌幅"] = pd.to_numeric(big_df["近6月涨跌幅"], errors="coerce")
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"], errors="coerce")
    big_df["近2年涨跌幅"] = pd.to_numeric(big_df["近2年涨跌幅"], errors="coerce")
    big_df["近3年涨跌幅"] = pd.to_numeric(big_df["近3年涨跌幅"], errors="coerce")
    big_df.sort_values(by=["日期"], inplace=True)
    big_df.drop_duplicates(inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


if __name__ == "__main__":
    # 企业商品价格指数
    macro_china_qyspjg_df = macro_china_qyspjg()
    print(macro_china_qyspjg_df)

    # 外商直接投资数据
    macro_china_fdi_df = macro_china_fdi()
    print(macro_china_fdi_df)

    # 社会融资规模增量
    macro_china_shrzgm_df = macro_china_shrzgm()
    print(macro_china_shrzgm_df)

    # 城镇调查失业率
    macro_china_urban_unemployment_df = macro_china_urban_unemployment()
    print(macro_china_urban_unemployment_df)

    # 金十数据中心-经济指标-中国-国民经济运行状况-经济状况-中国GDP年率报告
    macro_china_gdp_yearly_df = macro_china_gdp_yearly()
    print(macro_china_gdp_yearly_df)

    # 金十数据中心-经济指标-中国-国民经济运行状况-物价水平-中国CPI年率报告
    macro_china_cpi_yearly_df = macro_china_cpi_yearly()
    print(macro_china_cpi_yearly_df)

    # 金十数据中心-经济指标-中国-国民经济运行状况-物价水平-中国CPI月率报告
    macro_china_cpi_monthly_df = macro_china_cpi_monthly()
    print(macro_china_cpi_monthly_df)

    # 金十数据中心-经济指标-中国-国民经济运行状况-物价水平-中国PPI年率报告
    macro_china_ppi_yearly_df = macro_china_ppi_yearly()
    print(macro_china_ppi_yearly_df)

    # 金十数据中心-经济指标-中国-贸易状况-以美元计算出口年率报告
    macro_china_exports_yoy_df = macro_china_exports_yoy()
    print(macro_china_exports_yoy_df)

    # 金十数据中心-经济指标-中国-贸易状况-以美元计算进口年率
    macro_china_imports_yoy_df = macro_china_imports_yoy()
    print(macro_china_imports_yoy_df)

    # 金十数据中心-经济指标-中国-贸易状况-以美元计算贸易帐(亿美元)
    macro_china_trade_balance_df = macro_china_trade_balance()
    print(macro_china_trade_balance_df)

    # 金十数据中心-经济指标-中国-产业指标-规模以上工业增加值年率
    macro_china_industrial_production_yoy_df = macro_china_industrial_production_yoy()
    print(macro_china_industrial_production_yoy_df)

    # 金十数据中心-经济指标-中国-产业指标-官方制造业PMI
    macro_china_pmi_yearly_df = macro_china_pmi_yearly()
    print(macro_china_pmi_yearly_df)

    # 金十数据中心-经济指标-中国-产业指标-财新制造业PMI终值
    macro_china_cx_pmi_yearly_df = macro_china_cx_pmi_yearly()
    print(macro_china_cx_pmi_yearly_df)

    # 金十数据中心-经济指标-中国-产业指标-财新服务业PMI
    macro_china_cx_services_pmi_yearly_df = macro_china_cx_services_pmi_yearly()
    print(macro_china_cx_services_pmi_yearly_df)

    # 金十数据中心-经济指标-中国-产业指标-中国官方非制造业PMI
    macro_china_non_man_pmi_df = macro_china_non_man_pmi()
    print(macro_china_non_man_pmi_df)

    # 金十数据中心-经济指标-中国-金融指标-外汇储备(亿美元)
    macro_china_fx_reserves_yearly_df = macro_china_fx_reserves_yearly()
    print(macro_china_fx_reserves_yearly_df)

    # 金十数据中心-经济指标-中国-金融指标-M2货币供应年率
    macro_china_m2_yearly_df = macro_china_m2_yearly()
    print(macro_china_m2_yearly_df)

    # 金十数据中心-经济指标-中国-金融指标-上海银行业同业拆借报告
    macro_china_shibor_all_df = macro_china_shibor_all()
    print(macro_china_shibor_all_df)

    # 金十数据中心-经济指标-中国-金融指标-人民币香港银行同业拆息
    macro_china_hk_market_info_df = macro_china_hk_market_info()
    print(macro_china_hk_market_info_df)

    # 金十数据中心-经济指标-中国-其他-中国日度沿海六大电库存数据
    macro_china_daily_energy_df = macro_china_daily_energy()
    print(macro_china_daily_energy_df)

    # 金十数据中心-经济指标-中国-其他-中国人民币汇率中间价报告
    macro_china_rmb_df = macro_china_rmb()
    print(macro_china_rmb_df)

    # 金十数据中心-经济指标-中国-其他-深圳融资融券报告
    macro_china_market_margin_sz_df = macro_china_market_margin_sz()
    print(macro_china_market_margin_sz_df)

    # 金十数据中心-经济指标-中国-其他-上海融资融券报告
    macro_china_market_margin_sh_df = macro_china_market_margin_sh()
    print(macro_china_market_margin_sh_df)

    # 金十数据中心-经济指标-中国-其他-上海黄金交易所报告
    macro_china_au_report_df = macro_china_au_report()
    print(macro_china_au_report_df)

    # 中国-新房价指数
    macro_china_new_house_price_df = macro_china_new_house_price()
    print(macro_china_new_house_price_df)

    # 中国-企业景气及企业家信心指数
    macro_china_enterprise_boom_index_df = macro_china_enterprise_boom_index()
    print(macro_china_enterprise_boom_index_df)

    # 中国-全国税收收入
    macro_china_national_tax_receipts_df = macro_china_national_tax_receipts()
    print(macro_china_national_tax_receipts_df)

    # 中国-新增信贷数据
    macro_china_new_financial_credit_df = macro_china_new_financial_credit()
    print(macro_china_new_financial_credit_df)

    # 中国-外汇和黄金储备
    macro_china_fx_gold_df = macro_china_fx_gold()
    print(macro_china_fx_gold_df)

    macro_china_stock_market_cap_df = macro_china_stock_market_cap()
    print(macro_china_stock_market_cap_df)

    macro_china_money_supply_df = macro_china_money_supply()
    print(macro_china_money_supply_df)

    macro_china_cpi_df = macro_china_cpi()
    print(macro_china_cpi_df)

    macro_china_gdp_df = macro_china_gdp()
    print(macro_china_gdp_df)

    macro_china_ppi_df = macro_china_ppi()
    print(macro_china_ppi_df)

    macro_china_pmi_df = macro_china_pmi()
    print(macro_china_pmi_df)

    macro_china_gdzctz_df = macro_china_gdzctz()
    print(macro_china_gdzctz_df)

    macro_china_hgjck_df = macro_china_hgjck()
    print(macro_china_hgjck_df)

    macro_china_czsr_df = macro_china_czsr()
    print(macro_china_czsr_df)

    macro_china_whxd_df = macro_china_whxd()
    print(macro_china_whxd_df)

    macro_china_wbck_df = macro_china_wbck()
    print(macro_china_wbck_df)

    macro_china_xfzxx_df = macro_china_xfzxx()
    print(macro_china_xfzxx_df)

    macro_china_gyzjz_df = macro_china_gyzjz
    print(macro_china_gyzjz_df)

    macro_china_reserve_requirement_ratio_df = macro_china_reserve_requirement_ratio()
    print(macro_china_reserve_requirement_ratio_df)

    macro_china_consumer_goods_retail_df = macro_china_consumer_goods_retail()
    print(macro_china_consumer_goods_retail_df)

    macro_china_society_electricity_df = macro_china_society_electricity()
    print(macro_china_society_electricity_df)

    macro_china_society_traffic_volume_df = macro_china_society_traffic_volume()
    print(macro_china_society_traffic_volume_df)

    macro_china_postal_telecommunicational_df = macro_china_postal_telecommunicational()
    print(macro_china_postal_telecommunicational_df)

    macro_china_international_tourism_fx_df = macro_china_international_tourism_fx()
    print(macro_china_international_tourism_fx_df)

    macro_china_passenger_load_factor_df = macro_china_passenger_load_factor()
    print(macro_china_passenger_load_factor_df)

    macro_china_freight_index_df = macro_china_freight_index()
    print(macro_china_freight_index_df)

    macro_china_central_bank_balance_df = macro_china_central_bank_balance()
    print(macro_china_central_bank_balance_df)

    macro_china_insurance_df = macro_china_insurance()
    print(macro_china_insurance_df)

    macro_china_supply_of_money_df = macro_china_supply_of_money()
    print(macro_china_supply_of_money_df)

    macro_china_foreign_exchange_gold_df = macro_china_foreign_exchange_gold()
    print(macro_china_foreign_exchange_gold_df)

    macro_china_retail_price_index_df = macro_china_retail_price_index()
    print(macro_china_retail_price_index_df)

    macro_china_real_estate_df = macro_china_real_estate()
    print(macro_china_real_estate_df)

    macro_shipping_bci_df = macro_shipping_bci()
    print(macro_shipping_bci_df)

    macro_shipping_bdi_df = macro_shipping_bdi()
    print(macro_shipping_bdi_df)

    macro_shipping_bpi_df = macro_shipping_bpi()
    print(macro_shipping_bpi_df)

    macro_shipping_bcti_df = macro_shipping_bcti()
    print(macro_shipping_bcti_df)
