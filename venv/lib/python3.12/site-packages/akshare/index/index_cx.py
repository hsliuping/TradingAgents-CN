# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/6/4 18:30
Desc: 财新数据-指数报告-数字经济指数
https://yun.ccxe.com.cn/indices/dei
"""

import pandas as pd
import requests


def index_pmi_com_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-财新中国 PMI-综合 PMI
    https://yun.ccxe.com.cn/indices/pmi
    :return: 财新中国 PMI-综合 PMI
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "com"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "综合PMI", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "综合PMI",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_pmi_man_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-财新中国 PMI-制造业 PMI
    https://yun.ccxe.com.cn/indices/pmi
    :return: 财新中国 PMI-制造业 PMI
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "man"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "制造业PMI", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "制造业PMI",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_pmi_ser_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-财新中国 PMI-服务业 PMI
    https://yun.ccxe.com.cn/indices/pmi
    :return: 财新中国 PMI-服务业 PMI
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "ser"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "服务业PMI", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "服务业PMI",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_dei_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-数字经济指数
    https://yun.ccxe.com.cn/indices/dei
    :return: 数字经济指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "dei"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "数字经济指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "数字经济指数",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_ii_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-产业指数
    https://yun.ccxe.com.cn/indices/dei
    :return: 产业指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "ii"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "产业指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "产业指数",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_si_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-溢出指数
    https://yun.ccxe.com.cn/indices/dei
    :return: 溢出指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "si"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "溢出指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "溢出指数",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_fi_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-融合指数
    https://yun.ccxe.com.cn/indices/dei
    :return: 融合指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "fi"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "融合指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "融合指数",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_bi_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-基础指数
    https://yun.ccxe.com.cn/indices/dei
    :return: 基础指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "bi"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "基础指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "基础指数",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_nei_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-中国新经济指数
    https://yun.ccxe.com.cn/indices/nei
    :return: 中国新经济指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "nei"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "中国新经济指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "中国新经济指数",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_li_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-劳动力投入指数
    https://yun.ccxe.com.cn/indices/nei
    :return: 劳动力投入指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "li"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "劳动力投入指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "劳动力投入指数",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_ci_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-资本投入指数
    https://yun.ccxe.com.cn/indices/nei
    :return: 资本投入指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "ci"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "资本投入指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "资本投入指数",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_ti_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-科技投入指数
    https://yun.ccxe.com.cn/indices/nei
    :return: 科技投入指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "ti"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "科技投入指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "科技投入指数",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_neaw_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-新经济行业入职平均工资水平
    https://yun.ccxe.com.cn/indices/nei
    :return: 新经济行业入职平均工资水平
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "neaw"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "新经济行业入职平均工资水平", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "新经济行业入职平均工资水平",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_awpr_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-新经济入职工资溢价水平
    https://yun.ccxe.com.cn/indices/nei
    :return: 新经济入职工资溢价水平
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {"type": "awpr"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "新经济入职工资溢价水平", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "新经济入职工资溢价水平",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_cci_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-大宗商品指数
    https://yun.ccxe.com.cn/indices/nei
    :return: 大宗商品指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {
        "type": "cci",
        "code": "1000050",
        "month": "-1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化值", "大宗商品指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "大宗商品指数",
            "变化值",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_qli_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-高质量因子
    https://yun.ccxe.com.cn/indices/qli
    :return: 高质量因子
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {
        "type": "qli",
        "code": "1000050",
        "month": "-1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化幅度", "高质量因子指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "高质量因子指数",
            "变化幅度",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_ai_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-AI策略指数
    https://yun.ccxe.com.cn/indices/ai
    :return: AI策略指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {
        "type": "ai",
        "code": "1000050",
        "month": "-1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化幅度", "AI策略指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "AI策略指数",
            "变化幅度",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_bei_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-基石经济指数
    https://yun.ccxe.com.cn/indices/bei
    :return: 基石经济指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {
        "type": "ind",
        "code": "930927",
        "month": "-1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化幅度", "基石经济指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "基石经济指数",
            "变化幅度",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


def index_neei_cx() -> pd.DataFrame():
    """
    财新数据-指数报告-新动能指数
    https://yun.ccxe.com.cn/indices/neei
    :return: 新动能指数
    :rtype: pandas.DataFrame
    """
    url = "https://yun.ccxe.com.cn/api/index/pro/cxIndexTrendInfo"
    params = {
        "type": "ind",
        "code": "930928",
        "month": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.columns = ["变化幅度", "新动能指数", "日期"]
    temp_df = temp_df[
        [
            "日期",
            "新动能指数",
            "变化幅度",
        ]
    ]
    temp_df["日期"] = (
        pd.to_datetime(temp_df["日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    return temp_df


if __name__ == "__main__":
    index_pmi_com_cx_df = index_pmi_com_cx()
    print(index_pmi_com_cx_df)

    index_pmi_man_cx_df = index_pmi_man_cx()
    print(index_pmi_man_cx_df)

    index_pmi_ser_cx_df = index_pmi_ser_cx()
    print(index_pmi_ser_cx_df)

    index_dei_cx_df = index_dei_cx()
    print(index_dei_cx_df)

    index_ii_cx_df = index_ii_cx()
    print(index_ii_cx_df)

    index_si_cx_df = index_si_cx()
    print(index_si_cx_df)

    index_fi_cx_df = index_fi_cx()
    print(index_fi_cx_df)

    index_bi_cx_df = index_bi_cx()
    print(index_bi_cx_df)

    index_nei_cx_df = index_nei_cx()
    print(index_nei_cx_df)

    index_li_cx_df = index_li_cx()
    print(index_li_cx_df)

    index_ci_cx_df = index_ci_cx()
    print(index_ci_cx_df)

    index_ti_cx_df = index_ti_cx()
    print(index_ti_cx_df)

    index_neaw_cx_df = index_neaw_cx()
    print(index_neaw_cx_df)

    index_awpr_cx_df = index_awpr_cx()
    print(index_awpr_cx_df)

    index_cci_cx_df = index_cci_cx()
    print(index_cci_cx_df)

    index_qli_cx_df = index_qli_cx()
    print(index_qli_cx_df)

    index_ai_cx_df = index_ai_cx()
    print(index_ai_cx_df)

    index_bei_cx_df = index_bei_cx()
    print(index_bei_cx_df)

    index_neei_cx_df = index_neei_cx()
    print(index_neei_cx_df)
