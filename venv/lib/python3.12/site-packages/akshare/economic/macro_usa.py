#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/4 18:00
Desc: 金十数据中心-经济指标-美国
https://datacenter.jin10.com/economic
"""

import datetime
import time

import pandas as pd
import requests


def __macro_usa_base_func(symbol: str, params: dict) -> pd.DataFrame:
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


# 东方财富-美国-未决房屋销售月率
def macro_usa_phs() -> pd.DataFrame:
    """
    东方财富-经济数据一览-美国-未决房屋销售月率
    https://data.eastmoney.com/cjsj/foreign_0_5.html
    :return: 未决房屋销售月率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_USA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00342249")',
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
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
        "-",
        "-",
        "-",
        "时间",
        "-",
        "发布日期",
        "现值",
        "前值",
    ]
    temp_df = temp_df[
        [
            "时间",
            "前值",
            "现值",
            "发布日期",
        ]
    ]
    temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
    temp_df["现值"] = pd.to_numeric(temp_df["现值"], errors="coerce")
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"], errors="coerce").dt.date
    return temp_df


# 东方财富-经济指标-美国-物价水平-美国核心CPI月率报告
def macro_usa_cpi_yoy() -> pd.DataFrame:
    """
    东方财富-经济数据一览-美国-CPI年率, 数据区间从 2008-至今
    https://data.eastmoney.com/cjsj/foreign_0_12.html
    :return: 美国 CPI 年率报告
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_ECONOMICVALUE_USA",
        "columns": "ALL",
        "filter": '(INDICATOR_ID="EMG00000733")',
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    data_list = data_json["result"]["data"]
    temp_df = pd.DataFrame(
        data_list, columns=["REPORT_DATE", "PUBLISH_DATE", "VALUE", "PRE_VALUE"]
    )
    temp_df.columns = [
        "时间",
        "发布日期",
        "现值",
        "前值",
    ]
    temp_df["时间"] = pd.to_datetime(temp_df["时间"], errors="coerce").dt.date
    temp_df["发布日期"] = pd.to_datetime(temp_df["发布日期"], errors="coerce").dt.date
    temp_df["前值"] = pd.to_numeric(temp_df["前值"], errors="coerce")
    temp_df["现值"] = pd.to_numeric(temp_df["现值"], errors="coerce")
    temp_df.sort_values(by=["时间"], inplace=True, ignore_index=True)
    return temp_df


# 金十数据中心-经济指标-美国-经济状况-美国GDP
def macro_usa_gdp_monthly() -> pd.DataFrame:
    """
    金十数据-美国国内生产总值(GDP)报告, 数据区间从 20080228-至今
    https://datacenter.jin10.com/reportType/dc_usa_gdp
    :return: 美国国内生产总值(GDP)
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "53",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国国内生产总值(GDP)", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-物价水平-美国CPI月率报告
def macro_usa_cpi_monthly() -> pd.DataFrame:
    """
    美国 CPI 月率报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_cpi
    :return: 美国 CPI 月率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "9",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国CPI月率", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-物价水平-美国核心CPI月率报告
def macro_usa_core_cpi_monthly() -> pd.DataFrame:
    """
    美国核心 CPI 月率报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_core_cpi
    :return: 美国核心CPI月率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "6",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国核心CPI月率", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-物价水平-美国个人支出月率报告
def macro_usa_personal_spending() -> pd.DataFrame:
    """
    美国个人支出月率报告, 数据区间从19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_personal_spending
    :return: 美国个人支出月率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "35",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国个人支出月率", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-物价水平-美国零售销售月率报告
def macro_usa_retail_sales() -> pd.DataFrame:
    """
    美国零售销售月率报告, 数据区间从 19920301-至今
    https://datacenter.jin10.com/reportType/dc_usa_retail_sales
    :return: 美国零售销售月率报告-今值(%)
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "39",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国零售销售月率", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-物价水平-美国进口物价指数报告
def macro_usa_import_price() -> pd.DataFrame:
    """
    美国进口物价指数报告, 数据区间从19890201-至今
    https://datacenter.jin10.com/reportType/dc_usa_import_price
    :return: 美国进口物价指数报告-今值(%)
    :rtype: pandas.Series
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "18",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国进口物价指数", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-物价水平-美国出口价格指数报告
def macro_usa_export_price() -> pd.DataFrame:
    """
    美国出口价格指数报告, 数据区间从19890201-至今
    https://datacenter.jin10.com/reportType/dc_usa_export_price
    https://cdn.jin10.com/dc/reports/dc_usa_export_price_all.js?v=1578741832
    :return: 美国出口价格指数报告-今值(%)
    :rtype: pandas.Series
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "79",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国出口价格指数", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-劳动力市场-LMCI
def macro_usa_lmci() -> pd.DataFrame:
    """
    美联储劳动力市场状况指数报告, 数据区间从 20141006-至今
    https://datacenter.jin10.com/reportType/dc_usa_lmci
    :return: 美联储劳动力市场状况指数报告-今值(%)
    :rtype: pandas.Series
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "93",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美联储劳动力市场状况指数", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-劳动力市场-失业率-美国失业率报告
def macro_usa_unemployment_rate() -> pd.DataFrame:
    """
    美国失业率报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_unemployment_rate
    :return: 获取美国失业率报告
    :rtype: pandas.Series
    """
    t = time.time()
    params = {
        "category": "ec",
        "attr_id": "47",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国失业率", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-劳动力市场-失业率-美国挑战者企业裁员人数报告
def macro_usa_job_cuts() -> pd.DataFrame:
    """
    美国挑战者企业裁员人数报告, 数据区间从 19940201-至今
    https://datacenter.jin10.com/reportType/dc_usa_job_cuts
    :return: 美国挑战者企业裁员人数报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "category": "ec",
        "attr_id": "78",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国挑战者企业裁员人数", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-劳动力市场-就业人口-美国非农就业人数报告
def macro_usa_non_farm() -> pd.DataFrame:
    """
    美国非农就业人数报告, 数据区间从19700102-至今
    https://datacenter.jin10.com/reportType/dc_nonfarm_payrolls
    :return: 美国非农就业人数报告
    :rtype: pandas.Series
    """
    t = time.time()
    params = {
        "category": "ec",
        "attr_id": "33",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国非农就业人数", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-劳动力市场-就业人口-美国ADP就业人数报告
def macro_usa_adp_employment() -> pd.DataFrame:
    """
    美国ADP就业人数报告, 数据区间从 20010601-至今
    https://datacenter.jin10.com/reportType/dc_adp_nonfarm_employment
    :return: 美国ADP就业人数报告
    :rtype: pandas.Series
    """
    t = time.time()
    params = {
        "category": "ec",
        "attr_id": "1",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国ADP就业人数", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-劳动力市场-消费者收入与支出-美国核心PCE物价指数年率报告
def macro_usa_core_pce_price() -> pd.DataFrame:
    """
    美国核心PCE物价指数年率报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_core_pce_price
    :return: 美国核心PCE物价指数年率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "category": "ec",
        "attr_id": "80",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国核心PCE物价指数年率", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-劳动力市场-消费者收入与支出-美国实际个人消费支出季率初值报告
def macro_usa_real_consumer_spending() -> pd.DataFrame:
    """
    美国实际个人消费支出季率初值报告, 数据区间从 20131107-至今
    https://datacenter.jin10.com/reportType/dc_usa_real_consumer_spending
    :return: 美国实际个人消费支出季率初值报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "category": "ec",
        "attr_id": "81",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(
        symbol="美国实际个人消费支出季率初值", params=params
    )
    return temp_df


# 金十数据中心-经济指标-美国-贸易状况-美国贸易帐报告
def macro_usa_trade_balance() -> pd.DataFrame:
    """
    美国贸易帐报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_trade_balance
    :return: 美国贸易帐报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "category": "ec",
        "attr_id": "42",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国贸易帐报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-贸易状况-美国经常帐报告
def macro_usa_current_account() -> pd.DataFrame:
    """
    美国经常帐报告, 数据区间从 20080317-至今
    https://datacenter.jin10.com/reportType/dc_usa_current_account
    :return: 美国经常帐报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "category": "ec",
        "attr_id": "12",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国经常账报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-制造业-贝克休斯钻井报告
def macro_usa_rig_count() -> pd.DataFrame:
    """
    贝克休斯钻井报告, 数据区间从 20080317-至今
    https://datacenter.jin10.com/reportType/dc_rig_count_summary
    :return: 贝克休斯钻井报告-当周
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {"_": t}
    res = requests.get(
        url="https://cdn.jin10.com/data_center/reports/baker.json", params=params
    )
    temp_df = pd.DataFrame(res.json().get("values")).T
    big_df = pd.DataFrame()
    big_df["钻井总数_钻井数"] = temp_df["钻井总数"].apply(lambda x: x[0])
    big_df["钻井总数_变化"] = temp_df["钻井总数"].apply(lambda x: x[1])
    big_df["美国石油钻井_钻井数"] = temp_df["美国石油钻井"].apply(lambda x: x[0])
    big_df["美国石油钻井_变化"] = temp_df["美国石油钻井"].apply(lambda x: x[1])
    big_df["混合钻井_钻井数"] = temp_df["混合钻井"].apply(lambda x: x[0])
    big_df["混合钻井_变化"] = temp_df["混合钻井"].apply(lambda x: x[1])
    big_df["美国天然气钻井_钻井数"] = temp_df["美国天然气钻井"].apply(lambda x: x[0])
    big_df["美国天然气钻井_变化"] = temp_df["美国天然气钻井"].apply(lambda x: x[1])
    big_df = big_df.astype("float")
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    big_df.sort_values(by=["日期"], inplace=True, ignore_index=True)
    return big_df


# 金十数据中心-经济指标-美国-产业指标-制造业-美国生产者物价指数(PPI)报告
def macro_usa_ppi() -> pd.DataFrame:
    """
    美国生产者物价指数(PPI)报告, 数据区间从 20080226-至今
    https://datacenter.jin10.com/reportType/dc_usa_ppi
    :return: 美国生产者物价指数(PPI)报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "37",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国生产者物价指数", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-制造业-美国核心生产者物价指数(PPI)报告
def macro_usa_core_ppi() -> pd.DataFrame:
    """
    美国核心生产者物价指数(PPI)报告, 数据区间从20080318-至今
    https://datacenter.jin10.com/reportType/dc_usa_core_ppi
    :return: 美国核心生产者物价指数(PPI)报告-今值(%)
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "7",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国核心生产者物价指数", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-制造业-美国API原油库存报告
def macro_usa_api_crude_stock() -> pd.DataFrame:
    """
    美国 API 原油库存报告, 数据区间从 20120328-至今
    https://datacenter.jin10.com/reportType/dc_usa_api_crude_stock
    https://cdn.jin10.com/dc/reports/dc_usa_api_crude_stock_all.js?v=1578743859
    :return: 美国API原油库存报告-今值(万桶)
    :rtype: pandas.Series
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "69",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国API原油库存", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-制造业-美国Markit制造业PMI初值报告
def macro_usa_pmi() -> pd.DataFrame:
    """
    美国 Markit 制造业 PMI 初值报告, 数据区间从 20120601-至今
    https://datacenter.jin10.com/reportType/dc_usa_pmi
    :return: 美国 Markit 制造业 PMI 初值报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "74",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国Markit制造业PMI报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-制造业-美国ISM制造业PMI报告
def macro_usa_ism_pmi() -> pd.DataFrame:
    """
    美国 ISM 制造业 PMI 报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_ism_pmi
    :return: 美国 ISM 制造业 PMI 报告-今值
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "28",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国ISM制造业PMI报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-工业-美国工业产出月率报告
def macro_usa_industrial_production() -> pd.DataFrame:
    """
    美国工业产出月率报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_industrial_production
    :return: 美国工业产出月率报告-今值(%)
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "20",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国工业产出月率报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-工业-美国耐用品订单月率报告
def macro_usa_durable_goods_orders() -> pd.DataFrame:
    """
    美国耐用品订单月率报告, 数据区间从 20080227-至今
    https://datacenter.jin10.com/reportType/dc_usa_durable_goods_orders
    :return: 美国耐用品订单月率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "13",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国耐用品订单月率报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-工业-美国工厂订单月率报告
def macro_usa_factory_orders() -> pd.DataFrame:
    """
    美国工厂订单月率报告, 数据区间从 19920401-至今
    https://datacenter.jin10.com/reportType/dc_usa_factory_orders
    :return: 美国工厂订单月率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "16",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国工厂订单月率报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-服务业-美国Markit服务业PMI初值报告
def macro_usa_services_pmi() -> pd.DataFrame:
    """
    美国Markit服务业PMI初值报告, 数据区间从 20120701-至今
    https://datacenter.jin10.com/reportType/dc_usa_services_pmi
    :return: 美国Markit服务业PMI初值报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "89",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国Markit服务业PMI初值报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-服务业-美国商业库存月率报告
def macro_usa_business_inventories() -> pd.DataFrame:
    """
    美国商业库存月率报告, 数据区间从 19920301-至今
    https://datacenter.jin10.com/reportType/dc_usa_business_inventories
    :return: 美国商业库存月率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "4",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国商业库存月率报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-服务业-美国ISM非制造业PMI报告
def macro_usa_ism_non_pmi() -> pd.DataFrame:
    """
    美国ISM非制造业PMI报告, 数据区间从 19970801-至今
    https://datacenter.jin10.com/reportType/dc_usa_ism_non_pmi
    :return: 美国ISM非制造业PMI报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "29",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国ISM非制造业PMI报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-房地产-美国NAHB房产市场指数报告
def macro_usa_nahb_house_market_index() -> pd.DataFrame:
    """
    美国NAHB房产市场指数报告, 数据区间从 19850201-至今
    https://datacenter.jin10.com/reportType/dc_usa_nahb_house_market_index
    :return: 美国NAHB房产市场指数报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "31",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国NAHB房产市场指数报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-房地产-美国新屋开工总数年化报告
def macro_usa_house_starts() -> pd.DataFrame:
    """
    美国新屋开工总数年化报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_house_starts
    :return: 美国新屋开工总数年化报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "17",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国新屋开工总数年化报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-房地产-美国新屋销售总数年化报告
def macro_usa_new_home_sales() -> pd.DataFrame:
    """
    美国新屋销售总数年化报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_new_home_sales
    :return: 美国新屋销售总数年化报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "32",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国新屋销售总数年化报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-房地产-美国营建许可总数报告
def macro_usa_building_permits() -> pd.DataFrame:
    """
    美国营建许可总数报告, 数据区间从 20080220-至今
    https://datacenter.jin10.com/reportType/dc_usa_building_permits
    :return: 美国营建许可总数报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "3",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国营建许可总数报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-房地产-美国成屋销售总数年化报告
def macro_usa_exist_home_sales() -> pd.DataFrame:
    """
    美国成屋销售总数年化报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_exist_home_sales
    :return: 美国成屋销售总数年化报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "15",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国成屋销售总数年化报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-房地产-美国FHFA房价指数月率报告
def macro_usa_house_price_index() -> pd.DataFrame:
    """
    美国FHFA房价指数月率报告, 数据区间从 19910301-至今
    https://datacenter.jin10.com/reportType/dc_usa_house_price_index
    :return: 美国FHFA房价指数月率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "51",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国FHFA房价指数月率报告", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-房地产-美国S&P/CS20座大城市房价指数年率报告
def macro_usa_spcs20() -> pd.DataFrame:
    """
    美国S&P/CS20座大城市房价指数年率报告, 数据区间从 20010201-至今
    https://datacenter.jin10.com/reportType/dc_usa_spcs20
    :return: 美国S&P/CS20座大城市房价指数年率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "52",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(
        symbol="美国S&P/CS20座大城市房价指数年率", params=params
    )
    return temp_df


# 金十数据中心-经济指标-美国-产业指标-房地产-美国成屋签约销售指数月率报告
def macro_usa_pending_home_sales() -> pd.DataFrame:
    """
    美国成屋签约销售指数月率报告, 数据区间从 20010301-至今
    https://datacenter.jin10.com/reportType/dc_usa_pending_home_sales
    :return: 美国成屋签约销售指数月率报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "34",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(
        symbol="美国成屋签约销售指数月率报告", params=params
    )
    return temp_df


# 金十数据中心-经济指标-美国-领先指标-美国谘商会消费者信心指数报告
def macro_usa_cb_consumer_confidence() -> pd.DataFrame:
    """
    金十数据中心-经济指标-美国-领先指标-美国谘商会消费者信心指数报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_usa_cb_consumer_confidence
    :return: 美国谘商会消费者信心指数报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "5",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国谘商会消费者信心指数", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-领先指标-美国NFIB小型企业信心指数报告
def macro_usa_nfib_small_business() -> pd.DataFrame:
    """
    美国NFIB小型企业信心指数报告, 数据区间从 19750201-至今
    https://datacenter.jin10.com/reportType/dc_usa_nfib_small_business
    :return: 美国NFIB小型企业信心指数报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "63",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(
        symbol="美国NFIB小型企业信心指数报告", params=params
    )
    return temp_df


# 金十数据中心-经济指标-美国-领先指标-美国密歇根大学消费者信心指数初值报告
def macro_usa_michigan_consumer_sentiment() -> pd.DataFrame:
    """
    美国密歇根大学消费者信心指数初值报告, 数据区间从 19700301-至今
    https://datacenter.jin10.com/reportType/dc_usa_michigan_consumer_sentiment
    :return: 美国密歇根大学消费者信心指数初值报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "50",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(
        symbol="美国密歇根大学消费者信心指数初值报告", params=params
    )
    return temp_df


# 金十数据中心-经济指标-美国-其他-美国EIA原油库存报告
def macro_usa_eia_crude_rate() -> pd.DataFrame:
    """
    美国 EIA 原油库存报告, 数据区间从 19950801-至今
    https://datacenter.jin10.com/reportType/dc_eia_crude_oil
    :return: 美国 EIA 原油库存报告
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "10",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国EIA原油库存", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-其他-美国初请失业金人数报告
def macro_usa_initial_jobless() -> pd.DataFrame:
    """
    美国初请失业金人数报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_initial_jobless
    :return: 美国 EIA 原油库存报告
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": "44",
        "_": str(int(round(t * 1000))),
    }
    temp_df = __macro_usa_base_func(symbol="美国初请失业金人数", params=params)
    return temp_df


# 金十数据中心-经济指标-美国-其他-美国原油产量报告
def macro_usa_crude_inner() -> pd.DataFrame:
    """
    美国原油产量报告, 数据区间从 19830107-至今
    https://datacenter.jin10.com/reportType/dc_eia_crude_oil_produce
    :return: 美国原油产量报告
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {"_": t}
    res = requests.get(
        url="https://cdn.jin10.com/data_center/reports/usa_oil.json", params=params
    )
    temp_df = pd.DataFrame(res.json().get("values")).T
    big_df = pd.DataFrame()
    big_df["美国国内原油总量-产量"] = temp_df["美国国内原油总量"].apply(lambda x: x[0])
    big_df["美国国内原油总量-变化"] = temp_df["美国国内原油总量"].apply(lambda x: x[1])
    big_df["美国本土48州原油产量-产量"] = temp_df["美国本土48州原油产量"].apply(
        lambda x: x[0]
    )
    big_df["美国本土48州原油产量-变化"] = temp_df["美国本土48州原油产量"].apply(
        lambda x: x[1]
    )
    big_df["美国阿拉斯加州原油产量-产量"] = temp_df["美国阿拉斯加州原油产量"].apply(
        lambda x: x[0]
    )
    big_df["美国阿拉斯加州原油产量-变化"] = temp_df["美国阿拉斯加州原油产量"].apply(
        lambda x: x[1]
    )
    big_df = big_df.astype("float")
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    big_df.sort_values(by=["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-美国商品期货交易委员会CFTC外汇类非商业持仓报告
def macro_usa_cftc_nc_holding() -> pd.DataFrame:
    """
    美国商品期货交易委员会CFTC外汇类非商业持仓报告, 数据区间从 19830107-至今
    https://datacenter.jin10.com/reportType/dc_cftc_nc_report
    :return: 美国商品期货交易委员会CFTC外汇类非商业持仓报告
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {"_": str(int(round(t * 1000)))}
    r = requests.get(
        url="https://cdn.jin10.com/data_center/reports/cftc_4.json", params=params
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
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    big_df.sort_values(by=["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-美国商品期货交易委员会CFTC商品类非商业持仓报告
def macro_usa_cftc_c_holding() -> pd.DataFrame:
    """
    美国商品期货交易委员会CFTC商品类非商业持仓报告, 数据区间从 19830107-至今
    https://datacenter.jin10.com/reportType/dc_cftc_c_report
    :return: 美国商品期货交易委员会CFTC外汇类非商业持仓报告
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {"_": str(int(round(t * 1000)))}
    r = requests.get(
        url="https://cdn.jin10.com/data_center/reports/cftc_2.json", params=params
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
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    big_df.sort_values(by=["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-美国商品期货交易委员会CFTC外汇类商业持仓报告
def macro_usa_cftc_merchant_currency_holding() -> pd.DataFrame:
    """
    美国商品期货交易委员会CFTC外汇类商业持仓报告, 数据区间从 19860115-至今
    https://datacenter.jin10.com/reportType/dc_cftc_merchant_currency
    :return: 美国商品期货交易委员会CFTC外汇类商业持仓报告
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {"_": str(int(round(t * 1000)))}
    r = requests.get(
        url="https://cdn.jin10.com/data_center/reports/cftc_3.json", params=params
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
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    big_df.sort_values(by=["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-美国商品期货交易委员会CFTC商品类商业持仓报告
def macro_usa_cftc_merchant_goods_holding() -> pd.DataFrame:
    """
    美国商品期货交易委员会CFTC商品类商业持仓报告, 数据区间从 19860115-至今
    https://datacenter.jin10.com/reportType/dc_cftc_merchant_goods
    :return: 美国商品期货交易委员会CFTC商品类商业持仓报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    params = {"_": str(int(round(t * 1000)))}
    r = requests.get(
        url="https://cdn.jin10.com/data_center/reports/cftc_1.json", params=params
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
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    big_df.sort_values(by=["日期"], ignore_index=True, inplace=True)
    return big_df


# 金十数据中心-CME-贵金属
def macro_usa_cme_merchant_goods_holding():
    """
    CME-贵金属, 数据区间从 20180405-至今
    https://datacenter.jin10.com/org
    :return: CME-贵金属
    :return: pandas.DataFrame
    """
    t = time.time()
    params = {"_": str(int(round(t * 1000)))}
    r = requests.get(
        url="https://cdn.jin10.com/data_center/reports/cme_3.json", params=params
    )
    json_data = r.json()
    big_df = pd.DataFrame()
    for item in json_data["values"].keys():
        temp_df = pd.DataFrame(json_data["values"][item])
        temp_df["日期"] = item
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.columns = ["pz", "tc", "-", "-", "-", "成交量", "-", "-", "日期"]
    big_df["品种"] = big_df["pz"] + "-" + big_df["tc"]
    big_df = big_df[["日期", "品种", "成交量"]]
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


if __name__ == "__main__":
    # 东方财富-经济指标-美国-未决房屋销售月率
    macro_usa_phs_df = macro_usa_phs()
    print(macro_usa_phs_df)

    # 金十数据中心-经济指标-美国-经济状况-美国GDP
    macro_usa_gdp_monthly_df = macro_usa_gdp_monthly()
    print(macro_usa_gdp_monthly_df)

    # 金十数据中心-经济指标-美国-物价水平-美国CPI月率报告
    macro_usa_cpi_monthly_df = macro_usa_cpi_monthly()
    print(macro_usa_cpi_monthly_df)

    # 金十数据中心-经济指标-美国-物价水平-美国核心CPI月率报告
    macro_usa_core_cpi_monthly_df = macro_usa_core_cpi_monthly()
    print(macro_usa_core_cpi_monthly_df)

    # 金十数据中心-经济指标-美国-物价水平-美国个人支出月率报告
    macro_usa_personal_spending_df = macro_usa_personal_spending()
    print(macro_usa_personal_spending_df)

    # 金十数据中心-经济指标-美国-物价水平-美国零售销售月率报告
    macro_usa_retail_sales_df = macro_usa_retail_sales()
    print(macro_usa_retail_sales_df)

    # 金十数据中心-经济指标-美国-物价水平-美国进口物价指数报告
    macro_usa_import_price_df = macro_usa_import_price()
    print(macro_usa_import_price_df)

    # 金十数据中心-经济指标-美国-物价水平-美国出口价格指数报告
    macro_usa_export_price_df = macro_usa_export_price()
    print(macro_usa_export_price_df)

    # 金十数据中心-经济指标-美国-劳动力市场-LMCI
    macro_usa_lmci_df = macro_usa_lmci()
    print(macro_usa_lmci_df)

    # 金十数据中心-经济指标-美国-劳动力市场-失业率-美国失业率报告
    macro_usa_unemployment_rate_df = macro_usa_unemployment_rate()
    print(macro_usa_unemployment_rate_df)

    # 金十数据中心-经济指标-美国-劳动力市场-失业率-美国挑战者企业裁员人数报告
    macro_usa_job_cuts_df = macro_usa_job_cuts()
    print(macro_usa_job_cuts_df)

    # 金十数据中心-经济指标-美国-劳动力市场-就业人口-美国非农就业人数报告
    macro_usa_non_farm_df = macro_usa_non_farm()
    print(macro_usa_non_farm_df)

    # 金十数据中心-经济指标-美国-劳动力市场-就业人口-美国ADP就业人数报告
    macro_usa_adp_employment_df = macro_usa_adp_employment()
    print(macro_usa_adp_employment_df)

    # 金十数据中心-经济指标-美国-劳动力市场-消费者收入与支出-美国核心PCE物价指数年率报告
    macro_usa_core_pce_price_df = macro_usa_core_pce_price()
    print(macro_usa_core_pce_price_df)

    # 金十数据中心-经济指标-美国-劳动力市场-消费者收入与支出-美国实际个人消费支出季率初值报告
    macro_usa_real_consumer_spending_df = macro_usa_real_consumer_spending()
    print(macro_usa_real_consumer_spending_df)

    # 金十数据中心-经济指标-美国-贸易状况-美国贸易帐报告
    macro_usa_trade_balance_df = macro_usa_trade_balance()
    print(macro_usa_trade_balance_df)

    # 金十数据中心-经济指标-美国-贸易状况-美国经常帐报告
    macro_usa_current_account_df = macro_usa_current_account()
    print(macro_usa_current_account_df)

    # 金十数据中心-经济指标-美国-产业指标-制造业-贝克休斯钻井报告
    macro_usa_rig_count_df = macro_usa_rig_count()
    print(macro_usa_rig_count_df)

    # 金十数据中心-经济指标-美国-产业指标-制造业-美国生产者物价指数(PPI)报告
    macro_usa_ppi_df = macro_usa_ppi()
    print(macro_usa_ppi_df)

    # 金十数据中心-经济指标-美国-产业指标-制造业-美国核心生产者物价指数(PPI)报告
    macro_usa_core_ppi_df = macro_usa_core_ppi()
    print(macro_usa_core_ppi_df)

    # 金十数据中心-经济指标-美国-产业指标-制造业-美国API原油库存报告
    macro_usa_api_crude_stock_df = macro_usa_api_crude_stock()
    print(macro_usa_api_crude_stock_df)

    # 金十数据中心-经济指标-美国-产业指标-制造业-美国Markit制造业PMI初值报告
    macro_usa_pmi_df = macro_usa_pmi()
    print(macro_usa_pmi_df)

    # 金十数据中心-经济指标-美国-产业指标-制造业-美国ISM制造业PMI报告
    macro_usa_ism_pmi_df = macro_usa_ism_pmi()
    print(macro_usa_ism_pmi_df)

    # 金十数据中心-经济指标-美国-产业指标-房地产-美国NAHB房产市场指数报告
    macro_usa_nahb_house_market_index_df = macro_usa_nahb_house_market_index()
    print(macro_usa_nahb_house_market_index_df)

    # 金十数据中心-经济指标-美国-产业指标-房地产-美国新屋开工总数年化报告
    macro_usa_house_starts_df = macro_usa_house_starts()
    print(macro_usa_house_starts_df)

    # 金十数据中心-经济指标-美国-产业指标-房地产-美国新屋销售总数年化报告
    macro_usa_new_home_sales_df = macro_usa_new_home_sales()
    print(macro_usa_new_home_sales_df)

    # 金十数据中心-经济指标-美国-产业指标-房地产-美国营建许可总数报告
    macro_usa_building_permits_df = macro_usa_building_permits()
    print(macro_usa_building_permits_df)

    # 金十数据中心-经济指标-美国-产业指标-房地产-美国成屋销售总数年化报告
    macro_usa_exist_home_sales_df = macro_usa_exist_home_sales()
    print(macro_usa_exist_home_sales_df)

    # 金十数据中心-经济指标-美国-产业指标-房地产-美国FHFA房价指数月率报告
    macro_usa_house_price_index_df = macro_usa_house_price_index()
    print(macro_usa_house_price_index_df)

    # 金十数据中心-经济指标-美国-产业指标-房地产-美国S&P/CS20座大城市房价指数年率报告
    macro_usa_spcs20_df = macro_usa_spcs20()
    print(macro_usa_spcs20_df)

    # 金十数据中心-经济指标-美国-产业指标-房地产-美国成屋签约销售指数月率报告
    macro_usa_pending_home_sales_df = macro_usa_pending_home_sales()
    print(macro_usa_pending_home_sales_df)

    # 金十数据中心-经济指标-美国-领先指标-美国谘商会消费者信心指数报告
    macro_usa_cb_consumer_confidence_df = macro_usa_cb_consumer_confidence()
    print(macro_usa_cb_consumer_confidence_df)

    # 金十数据中心-经济指标-美国-领先指标-美国NFIB小型企业信心指数报告
    macro_usa_nfib_small_business_df = macro_usa_nfib_small_business()
    print(macro_usa_nfib_small_business_df)

    # 金十数据中心-经济指标-美国-领先指标-美国密歇根大学消费者信心指数初值报告
    macro_usa_michigan_consumer_sentiment_df = macro_usa_michigan_consumer_sentiment()
    print(macro_usa_michigan_consumer_sentiment_df)

    # 金十数据中心-经济指标-美国-其他-美国EIA原油库存报告
    macro_usa_eia_crude_rate_df = macro_usa_eia_crude_rate()
    print(macro_usa_eia_crude_rate_df)

    # 金十数据中心-经济指标-美国-其他-美国初请失业金人数报告
    macro_usa_initial_jobless_df = macro_usa_initial_jobless()
    print(macro_usa_initial_jobless_df)

    # 金十数据中心-经济指标-美国-其他-美国原油产量报告
    macro_usa_crude_inner_df = macro_usa_crude_inner()
    print(macro_usa_crude_inner_df)

    # 金十数据中心-美国商品期货交易委员会CFTC外汇类非商业持仓报告
    macro_usa_cftc_nc_holding_df = macro_usa_cftc_nc_holding()
    print(macro_usa_cftc_nc_holding_df)

    # 金十数据中心-美国商品期货交易委员会CFTC商品类非商业持仓报告
    macro_usa_cftc_c_holding_df = macro_usa_cftc_c_holding()
    print(macro_usa_cftc_c_holding_df)

    # 金十数据中心-美国商品期货交易委员会CFTC外汇类商业持仓报告
    macro_usa_cftc_merchant_currency_holding_df = (
        macro_usa_cftc_merchant_currency_holding()
    )
    print(macro_usa_cftc_merchant_currency_holding_df)

    # 金十数据中心-美国商品期货交易委员会CFTC商品类商业持仓报告
    macro_usa_cftc_merchant_goods_holding_df = macro_usa_cftc_merchant_goods_holding()
    print(macro_usa_cftc_merchant_goods_holding_df)

    # 金十数据中心-CME-贵金属
    macro_usa_cme_merchant_goods_holding_df = macro_usa_cme_merchant_goods_holding()
    print(macro_usa_cme_merchant_goods_holding_df)
