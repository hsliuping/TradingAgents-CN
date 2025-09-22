#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/11/5 17:11
Desc: 金十数据中心-经济指标-央行利率-主要央行利率
https://datacenter.jin10.com/economic
输出数据格式为 float64
美联储利率决议报告
欧洲央行决议报告
新西兰联储决议报告
中国央行决议报告
瑞士央行决议报告
英国央行决议报告
澳洲联储决议报告
日本央行决议报告
俄罗斯央行决议报告
印度央行决议报告
巴西央行决议报告
"""

import datetime
import time

import pandas as pd
import requests


def __get_interest_rate_data(attr_id: str, name: str = "利率") -> pd.DataFrame:
    """
    利率决议报告公共函数
    https://datacenter.jin10.com/reportType/dc_usa_interest_rate_decision
    :param attr_id: 内置属性
    :type attr_id: str
    :param name: 利率报告名称
    :type name: str
    :return: 利率决议报告数据
    :rtype: pandas.Series
    """
    t = time.time()
    headers = {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://datacenter.jin10.com",
        "Referer": "https://datacenter.jin10.com/",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-version": "1.0.0",
    }
    base_url = "https://datacenter-api.jin10.com/reports/list_v2"
    params = {
        "max_date": "",
        "category": "ec",
        "attr_id": attr_id,
        "_": str(int(round(t * 1000))),
    }
    interest_rate_data = []
    try:
        while True:
            response = requests.get(
                url=base_url, params=params, headers=headers, timeout=10
            )
            data = response.json()
            if not data.get("data", {}).get("values"):
                break
            interest_rate_data.extend(data["data"]["values"])

            # Update max_date for pagination
            last_date = data["data"]["values"][-1][0]
            next_date = (
                datetime.datetime.strptime(last_date, "%Y-%m-%d").date()
                - datetime.timedelta(days=1)
            ).isoformat()
            params["max_date"] = next_date

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

    # Convert to DataFrame
    big_df = pd.DataFrame(interest_rate_data)

    if big_df.empty:
        return pd.DataFrame()

    # Process DataFrame
    big_df["商品"] = name
    big_df.columns = ["日期", "今值", "预测值", "前值", "商品"]
    big_df = big_df[["商品", "日期", "今值", "预测值", "前值"]]

    # Convert data types
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    numeric_columns = ["今值", "预测值", "前值"]
    for col in numeric_columns:
        big_df[col] = pd.to_numeric(big_df[col], errors="coerce")

    return big_df.sort_values("日期").reset_index(drop=True)


# 金十数据中心-经济指标-央行利率-主要央行利率-美联储利率决议报告
def macro_bank_usa_interest_rate() -> pd.DataFrame:
    """
    美联储利率决议报告, 数据区间从 19820927-至今
    https://datacenter.jin10.com/reportType/dc_usa_interest_rate_decision
    :return: 美联储利率决议报告-今值(%)
    :rtype: pandas.Series
    """
    return __get_interest_rate_data(attr_id="24", name="美联储利率决议报告")


# 金十数据中心-经济指标-央行利率-主要央行利率-欧洲央行决议报告
def macro_bank_euro_interest_rate() -> pd.DataFrame:
    """
    欧洲央行决议报告, 数据区间从 19990101-至今
    https://datacenter.jin10.com/reportType/dc_interest_rate_decision
    https://cdn.jin10.com/dc/reports/dc_interest_rate_decision_all.js?v=1578581663
    :return: 欧洲央行决议报告-今值(%)
    :rtype: pandas.Series
    """
    return __get_interest_rate_data(attr_id="21", name="欧洲央行决议报告")


# 金十数据中心-经济指标-央行利率-主要央行利率-新西兰联储决议报告
def macro_bank_newzealand_interest_rate() -> pd.DataFrame:
    """
    新西兰联储决议报告, 数据区间从 19990401-至今
    https://datacenter.jin10.com/reportType/dc_newzealand_interest_rate_decision
    https://cdn.jin10.com/dc/reports/dc_newzealand_interest_rate_decision_all.js?v=1578582075
    :return: 新西兰联储决议报告-今值(%)
    :rtype: pandas.Series
    """
    return __get_interest_rate_data(attr_id="23", name="新西兰利率决议报告")


# 金十数据中心-经济指标-央行利率-主要央行利率-中国央行决议报告
def macro_bank_china_interest_rate() -> pd.DataFrame:
    """
    中国央行决议报告, 数据区间从 19990105-至今
    https://datacenter.jin10.com/reportType/dc_newzealand_interest_rate_decision
    https://cdn.jin10.com/dc/reports/dc_newzealand_interest_rate_decision_all.js?v=1578582075
    :return: 新西兰联储决议报告-今值(%)
    :rtype: pandas.Series
    """
    return __get_interest_rate_data(attr_id="91", name="中国央行决议报告")


# 金十数据中心-经济指标-央行利率-主要央行利率-瑞士央行决议报告
def macro_bank_switzerland_interest_rate() -> pd.DataFrame:
    """
    瑞士央行利率决议报告, 数据区间从 20080313-至今
    https://datacenter.jin10.com/reportType/dc_switzerland_interest_rate_decision
    https://cdn.jin10.com/dc/reports/dc_switzerland_interest_rate_decision_all.js?v=1578582240
    :return: 瑞士央行利率决议报告-今值(%)
    :rtype: pandas.Series
    """
    return __get_interest_rate_data(attr_id="25", name="瑞士央行决议报告")


# 金十数据中心-经济指标-央行利率-主要央行利率-英国央行决议报告
def macro_bank_english_interest_rate() -> pd.DataFrame:
    """
    英国央行决议报告, 数据区间从 19700101-至今
    https://datacenter.jin10.com/reportType/dc_english_interest_rate_decision
    https://cdn.jin10.com/dc/reports/dc_english_interest_rate_decision_all.js?v=1578582331
    :return: 英国央行决议报告-今值(%)
    :rtype: pandas.Series
    """
    return __get_interest_rate_data(attr_id="26", name="英国央行决议报告")


# 金十数据中心-经济指标-央行利率-主要央行利率-澳洲联储决议报告
def macro_bank_australia_interest_rate() -> pd.DataFrame:
    """
    澳洲联储决议报告, 数据区间从 19800201-至今
    https://datacenter.jin10.com/reportType/dc_australia_interest_rate_decision
    https://cdn.jin10.com/dc/reports/dc_australia_interest_rate_decision_all.js?v=1578582414
    :return: 澳洲联储决议报告-今值(%)
    :rtype: pandas.Series
    """
    return __get_interest_rate_data(attr_id="27", name="澳洲联储决议报告")


# 金十数据中心-经济指标-央行利率-主要央行利率-日本央行决议报告
def macro_bank_japan_interest_rate() -> pd.DataFrame:
    """
    日本利率决议报告, 数据区间从 20080214-至今
    https://datacenter.jin10.com/reportType/dc_japan_interest_rate_decision
    https://cdn.jin10.com/dc/reports/dc_japan_interest_rate_decision_all.js?v=1578582485
    :return: 日本利率决议报告-今值(%)
    :rtype: pandas.Series
    """
    return __get_interest_rate_data(attr_id="22", name="日本央行决议报告")


# 金十数据中心-经济指标-央行利率-主要央行利率-俄罗斯央行决议报告
def macro_bank_russia_interest_rate() -> pd.DataFrame:
    """
    俄罗斯利率决议报告, 数据区间从 20030601-至今
    https://datacenter.jin10.com/reportType/dc_russia_interest_rate_decision
    https://cdn.jin10.com/dc/reports/dc_russia_interest_rate_decision_all.js?v=1578582572
    :return: 俄罗斯利率决议报告-今值(%)
    :rtype: pandas.Series
    """
    return __get_interest_rate_data(attr_id="64", name="俄罗斯央行决议报告")


# 金十数据中心-经济指标-央行利率-主要央行利率-印度央行决议报告
def macro_bank_india_interest_rate() -> pd.DataFrame:
    """
    印度利率决议报告, 数据区间从 20000801-至今
    https://datacenter.jin10.com/reportType/dc_india_interest_rate_decision
    https://cdn.jin10.com/dc/reports/dc_india_interest_rate_decision_all.js?v=1578582645
    :return: 印度利率决议报告-今值(%)
    :rtype: pandas.Series
    """
    return __get_interest_rate_data(attr_id="68", name="印度央行决议报告")


# 金十数据中心-经济指标-央行利率-主要央行利率-巴西央行决议报告
def macro_bank_brazil_interest_rate() -> pd.DataFrame:
    """
    巴西利率决议报告, 数据区间从 20080201-至今
    https://datacenter.jin10.com/reportType/dc_brazil_interest_rate_decision
    https://cdn.jin10.com/dc/reports/dc_brazil_interest_rate_decision_all.js?v=1578582718
    :return: 巴西利率决议报告-今值(%)
    :rtype: pandas.Series
    """
    return __get_interest_rate_data(attr_id="55", name="巴西央行决议报告")


if __name__ == "__main__":
    # 金十数据中心-经济指标-央行利率-主要央行利率-美联储利率决议报告
    macro_bank_usa_interest_rate_df = macro_bank_usa_interest_rate()
    print(macro_bank_usa_interest_rate_df)

    # 金十数据中心-经济指标-央行利率-主要央行利率-欧洲央行决议报告
    macro_bank_euro_interest_rate_df = macro_bank_euro_interest_rate()
    print(macro_bank_euro_interest_rate_df)

    # 金十数据中心-经济指标-央行利率-主要央行利率-新西兰联储决议报告
    macro_bank_newzealand_interest_rate_df = macro_bank_newzealand_interest_rate()
    print(macro_bank_newzealand_interest_rate_df)

    # 金十数据中心-经济指标-央行利率-主要央行利率-中国央行决议报告
    macro_bank_china_interest_rate_df = macro_bank_china_interest_rate()
    print(macro_bank_china_interest_rate_df)

    # 金十数据中心-经济指标-央行利率-主要央行利率-瑞士央行决议报告
    macro_bank_switzerland_interest_rate_df = macro_bank_switzerland_interest_rate()
    print(macro_bank_switzerland_interest_rate_df)

    # 金十数据中心-经济指标-央行利率-主要央行利率-英国央行决议报告
    macro_bank_english_interest_rate_df = macro_bank_english_interest_rate()
    print(macro_bank_english_interest_rate_df)

    # 金十数据中心-经济指标-央行利率-主要央行利率-澳洲联储决议报告
    macro_bank_australia_interest_rate_df = macro_bank_australia_interest_rate()
    print(macro_bank_australia_interest_rate_df)

    # 金十数据中心-经济指标-央行利率-主要央行利率-日本央行决议报告
    macro_bank_japan_interest_rate_df = macro_bank_japan_interest_rate()
    print(macro_bank_japan_interest_rate_df)

    # 金十数据中心-经济指标-央行利率-主要央行利率-俄罗斯央行决议报告
    macro_bank_russia_interest_rate_df = macro_bank_russia_interest_rate()
    print(macro_bank_russia_interest_rate_df)

    # 金十数据中心-经济指标-央行利率-主要央行利率-印度央行决议报告
    macro_bank_india_interest_rate_df = macro_bank_india_interest_rate()
    print(macro_bank_india_interest_rate_df)

    # 金十数据中心-经济指标-央行利率-主要央行利率-巴西央行决议报告
    macro_bank_brazil_interest_rate_df = macro_bank_brazil_interest_rate()
    print(macro_bank_brazil_interest_rate_df)
