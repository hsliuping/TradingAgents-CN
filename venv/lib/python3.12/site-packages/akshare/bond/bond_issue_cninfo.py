# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/6/19 22:00
Desc: 巨潮资讯-数据中心-专题统计-债券报表-债券发行
http://webapi.cninfo.com.cn/#/thematicStatistics
"""

import pandas as pd
import requests
import py_mini_racer

from akshare.datasets import get_ths_js


def _get_file_content_cninfo(file: str = "cninfo.js") -> str:
    """
    获取 JS 文件的内容
    :param file:  JS 文件名
    :type file: str
    :return: 文件内容
    :rtype: str
    """
    setting_file_path = get_ths_js(file)
    with open(setting_file_path, encoding="utf-8") as f:
        file_data = f.read()
    return file_data


def bond_treasure_issue_cninfo(
    start_date: str = "20210910", end_date: str = "20211109"
) -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-债券报表-债券发行-国债发行
    http://webapi.cninfo.com.cn/#/thematicStatistics
    :param start_date: 开始统计时间
    :type start_date: str
    :param end_date: 结束统计数据
    :type end_date: str
    :return: 国债发行
    :rtype: pandas.DataFrame
    """
    url = "http://webapi.cninfo.com.cn/api/sysapi/p_sysapi1120"
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_cninfo("cninfo.js")
    js_code.eval(js_content)
    mcode = js_code.call("getResCode1")
    headers = {
        "Accept": "*/*",
        "Accept-Enckey": mcode,
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "Origin": "http://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "sdate": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "edate": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.rename(
        columns={
            "F009D": "缴款日",
            "SECNAME": "债券简称",
            "DECLAREDATE": "公告日期",
            "F004D": "发行起始日",
            "F003D": "发行终止日",
            "F008N": "单位面值",
            "SECCODE": "债券代码",
            "F007N": "发行价格",
            "F006N": "计划发行总量",
            "F005N": "实际发行总量",
            "F028N": "增发次数",
            "BONDNAME": "债券名称",
            "F014V": "发行对象",
            "F002V": "交易市场",
            "F013V": "发行方式",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "债券代码",
            "债券简称",
            "发行起始日",
            "发行终止日",
            "计划发行总量",
            "实际发行总量",
            "发行价格",
            "单位面值",
            "缴款日",
            "增发次数",
            "交易市场",
            "发行方式",
            "发行对象",
            "公告日期",
            "债券名称",
        ]
    ]
    temp_df["发行起始日"] = pd.to_datetime(
        temp_df["发行起始日"], errors="coerce"
    ).dt.date
    temp_df["发行终止日"] = pd.to_datetime(
        temp_df["发行终止日"], errors="coerce"
    ).dt.date
    temp_df["缴款日"] = pd.to_datetime(temp_df["缴款日"], errors="coerce").dt.date
    temp_df["公告日期"] = pd.to_datetime(temp_df["公告日期"], errors="coerce").dt.date
    temp_df["计划发行总量"] = pd.to_numeric(temp_df["计划发行总量"], errors="coerce")
    temp_df["实际发行总量"] = pd.to_numeric(temp_df["实际发行总量"], errors="coerce")
    temp_df["发行价格"] = pd.to_numeric(temp_df["发行价格"], errors="coerce")
    temp_df["单位面值"] = pd.to_numeric(temp_df["单位面值"], errors="coerce")
    temp_df["增发次数"] = pd.to_numeric(temp_df["增发次数"], errors="coerce")
    return temp_df


def bond_local_government_issue_cninfo(
    start_date: str = "20210911", end_date: str = "20211110"
) -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-债券报表-债券发行-地方债发行
    http://webapi.cninfo.com.cn/#/thematicStatistics
    :param start_date: 开始统计时间
    :type start_date: str
    :param end_date: 开始统计时间
    :type end_date: str
    :return: 地方债发行
    :rtype: pandas.DataFrame
    """
    url = "http://webapi.cninfo.com.cn/api/sysapi/p_sysapi1121"
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_cninfo("cninfo.js")
    js_code.eval(js_content)
    mcode = js_code.call("getResCode1")
    headers = {
        "Accept": "*/*",
        "Accept-Enckey": mcode,
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "Origin": "http://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "sdate": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "edate": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.rename(
        columns={
            "F009D": "缴款日",
            "SECNAME": "债券简称",
            "DECLAREDATE": "公告日期",
            "F004D": "发行起始日",
            "F003D": "发行终止日",
            "F008N": "单位面值",
            "SECCODE": "债券代码",
            "F007N": "发行价格",
            "F006N": "计划发行总量",
            "F005N": "实际发行总量",
            "F028N": "增发次数",
            "BONDNAME": "债券名称",
            "F014V": "发行对象",
            "F002V": "交易市场",
            "F013V": "发行方式",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "债券代码",
            "债券简称",
            "发行起始日",
            "发行终止日",
            "计划发行总量",
            "实际发行总量",
            "发行价格",
            "单位面值",
            "缴款日",
            "增发次数",
            "交易市场",
            "发行方式",
            "发行对象",
            "公告日期",
            "债券名称",
        ]
    ]
    temp_df["发行起始日"] = pd.to_datetime(
        temp_df["发行起始日"], errors="coerce"
    ).dt.date
    temp_df["发行终止日"] = pd.to_datetime(
        temp_df["发行终止日"], errors="coerce"
    ).dt.date
    temp_df["缴款日"] = pd.to_datetime(temp_df["缴款日"], errors="coerce").dt.date
    temp_df["公告日期"] = pd.to_datetime(temp_df["公告日期"], errors="coerce").dt.date
    temp_df["计划发行总量"] = pd.to_numeric(temp_df["计划发行总量"], errors="coerce")
    temp_df["实际发行总量"] = pd.to_numeric(temp_df["实际发行总量"], errors="coerce")
    temp_df["发行价格"] = pd.to_numeric(temp_df["发行价格"], errors="coerce")
    temp_df["单位面值"] = pd.to_numeric(temp_df["单位面值"], errors="coerce")
    temp_df["增发次数"] = pd.to_numeric(temp_df["增发次数"], errors="coerce")
    return temp_df


def bond_corporate_issue_cninfo(
    start_date: str = "20210911", end_date: str = "20211110"
) -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-债券报表-债券发行-企业债发行
    http://webapi.cninfo.com.cn/#/thematicStatistics
    :param start_date: 开始统计时间
    :type start_date: str
    :param end_date: 开始统计时间
    :type end_date: str
    :return: 企业债发行
    :rtype: pandas.DataFrame
    """
    url = "http://webapi.cninfo.com.cn/api/sysapi/p_sysapi1122"
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_cninfo("cninfo.js")
    js_code.eval(js_content)
    mcode = js_code.call("getResCode1")
    headers = {
        "Accept": "*/*",
        "Accept-Enckey": mcode,
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "Origin": "http://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "sdate": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "edate": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.rename(
        columns={
            "SECNAME": "债券简称",
            "DECLAREDATE": "公告日期",
            "F004D": "交易所网上发行终止日",
            "F003D": "交易所网上发行起始日",
            "F008N": "发行面值",
            "SECCODE": "债券代码",
            "F007N": "发行价格",
            "F006N": "实际发行总量",
            "F005N": "计划发行总量",
            "F022N": "最小认购单位",
            "F017V": "承销方式",
            "F052N": "最低认购额",
            "F015V": "发行范围",
            "BONDNAME": "债券名称",
            "F014V": "发行对象",
            "F013V": "发行方式",
            "F023V": "募资用途说明",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "债券代码",
            "债券简称",
            "公告日期",
            "交易所网上发行起始日",
            "交易所网上发行终止日",
            "计划发行总量",
            "实际发行总量",
            "发行面值",
            "发行价格",
            "发行方式",
            "发行对象",
            "发行范围",
            "承销方式",
            "最小认购单位",
            "募资用途说明",
            "最低认购额",
            "债券名称",
        ]
    ]
    temp_df["公告日期"] = pd.to_datetime(temp_df["公告日期"], errors="coerce").dt.date
    temp_df["交易所网上发行起始日"] = pd.to_datetime(
        temp_df["交易所网上发行起始日"], errors="coerce"
    ).dt.date
    temp_df["交易所网上发行终止日"] = pd.to_datetime(
        temp_df["交易所网上发行终止日"], errors="coerce"
    ).dt.date
    temp_df["计划发行总量"] = pd.to_numeric(temp_df["计划发行总量"], errors="coerce")
    temp_df["实际发行总量"] = pd.to_numeric(temp_df["实际发行总量"], errors="coerce")
    temp_df["发行面值"] = pd.to_numeric(temp_df["发行面值"], errors="coerce")
    temp_df["发行价格"] = pd.to_numeric(temp_df["发行价格"], errors="coerce")
    temp_df["最小认购单位"] = pd.to_numeric(temp_df["最小认购单位"], errors="coerce")
    temp_df["最低认购额"] = pd.to_numeric(temp_df["最低认购额"], errors="coerce")
    return temp_df


def bond_cov_issue_cninfo(
    start_date: str = "20210913", end_date: str = "20211112"
) -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-债券报表-债券发行-可转债发行
    http://webapi.cninfo.com.cn/#/thematicStatistics
    :param start_date: 开始统计时间
    :type start_date: str
    :param end_date: 开始统计时间
    :type end_date: str
    :return: 可转债发行
    :rtype: pandas.DataFrame
    """
    url = "http://webapi.cninfo.com.cn/api/sysapi/p_sysapi1123"
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_cninfo("cninfo.js")
    js_code.eval(js_content)
    mcode = js_code.call("getResCode1")
    headers = {
        "Accept": "*/*",
        "Accept-Enckey": mcode,
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "Origin": "http://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "sdate": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "edate": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.rename(
        columns={
            "F029D": "发行起始日",
            "SECNAME": "债券简称",
            "F027D": "转股开始日期",
            "F003D": "发行终止日",
            "F007N": "发行面值",
            "F053D": "转股终止日期",
            "F005N": "计划发行总量",
            "F051D": "网上申购日期",
            "F026N": "初始转股价格",
            "F066N": "网上申购数量下限",
            "F052N": "发行价格",
            "BONDNAME": "债券名称",
            "F014V": "发行对象",
            "F002V": "交易市场",
            "F032V": "网上申购简称",
            "F086V": "转股代码",
            "DECLAREDATE": "公告日期",
            "F028D": "债权登记日",
            "F004D": "优先申购日",
            "F068D": "网上申购中签结果公告日及退款日",
            "F054D": "优先申购缴款日",
            "F008N": "网上申购数量上限",
            "SECCODE": "债券代码",
            "F006N": "实际发行总量",
            "F067N": "网上申购单位",
            "F065N": "配售价格",
            "F017V": "承销方式",
            "F015V": "发行范围",
            "F013V": "发行方式",
            "F021V": "募资用途说明",
            "F031V": "网上申购代码",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "债券代码",
            "债券简称",
            "公告日期",
            "发行起始日",
            "发行终止日",
            "计划发行总量",
            "实际发行总量",
            "发行面值",
            "发行价格",
            "发行方式",
            "发行对象",
            "发行范围",
            "承销方式",
            "募资用途说明",
            "初始转股价格",
            "转股开始日期",
            "转股终止日期",
            "网上申购日期",
            "网上申购代码",
            "网上申购简称",
            "网上申购数量上限",
            "网上申购数量下限",
            "网上申购单位",
            "网上申购中签结果公告日及退款日",
            "优先申购日",
            "配售价格",
            "债权登记日",
            "优先申购缴款日",
            "转股代码",
            "交易市场",
            "债券名称",
        ]
    ]
    temp_df["公告日期"] = pd.to_datetime(temp_df["公告日期"], errors="coerce").dt.date
    temp_df["发行起始日"] = pd.to_datetime(
        temp_df["发行起始日"], errors="coerce"
    ).dt.date
    temp_df["发行终止日"] = pd.to_datetime(
        temp_df["发行终止日"], errors="coerce"
    ).dt.date
    temp_df["转股开始日期"] = pd.to_datetime(
        temp_df["转股开始日期"], errors="coerce"
    ).dt.date
    temp_df["转股终止日期"] = pd.to_datetime(
        temp_df["转股终止日期"], errors="coerce"
    ).dt.date
    temp_df["转股终止日期"] = pd.to_datetime(
        temp_df["转股终止日期"], errors="coerce"
    ).dt.date
    temp_df["网上申购日期"] = pd.to_datetime(
        temp_df["网上申购日期"], errors="coerce"
    ).dt.date
    temp_df["网上申购中签结果公告日及退款日"] = pd.to_datetime(
        temp_df["网上申购中签结果公告日及退款日"], errors="coerce"
    ).dt.date
    temp_df["债权登记日"] = pd.to_datetime(
        temp_df["债权登记日"], errors="coerce"
    ).dt.date
    temp_df["优先申购日"] = pd.to_datetime(
        temp_df["优先申购日"], errors="coerce"
    ).dt.date
    temp_df["优先申购缴款日"] = pd.to_datetime(
        temp_df["优先申购缴款日"], errors="coerce"
    ).dt.date
    temp_df["计划发行总量"] = pd.to_numeric(temp_df["计划发行总量"], errors="coerce")
    temp_df["实际发行总量"] = pd.to_numeric(temp_df["实际发行总量"], errors="coerce")
    temp_df["发行面值"] = pd.to_numeric(temp_df["发行面值"], errors="coerce")
    temp_df["发行价格"] = pd.to_numeric(temp_df["发行价格"], errors="coerce")
    temp_df["初始转股价格"] = pd.to_numeric(temp_df["初始转股价格"], errors="coerce")
    temp_df["网上申购数量上限"] = pd.to_numeric(
        temp_df["网上申购数量上限"], errors="coerce"
    )
    temp_df["网上申购数量下限"] = pd.to_numeric(
        temp_df["网上申购数量下限"], errors="coerce"
    )
    temp_df["网上申购单位"] = pd.to_numeric(temp_df["网上申购单位"], errors="coerce")
    temp_df["配售价格"] = pd.to_numeric(temp_df["配售价格"], errors="coerce")
    return temp_df


def bond_cov_stock_issue_cninfo() -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-债券报表-债券发行-可转债转股
    http://webapi.cninfo.com.cn/#/thematicStatistics
    :return: 可转债转股
    :rtype: pandas.DataFrame
    """
    url = "http://webapi.cninfo.com.cn/api/sysapi/p_sysapi1124"
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_cninfo("cninfo.js")
    js_code.eval(js_content)
    mcode = js_code.call("getResCode1")
    headers = {
        "Accept": "*/*",
        "Accept-Enckey": mcode,
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "Origin": "http://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.post(url, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.rename(
        columns={
            "F003N": "转股价格",
            "SECNAME": "债券简称",
            "DECLAREDATE": "公告日期",
            "F005D": "自愿转换期终止日",
            "F004D": "自愿转换期起始日",
            "F017V": "标的股票",
            "BONDNAME": "债券名称",
            "F002V": "转股简称",
            "F001V": "转股代码",
            "SECCODE": "债券代码",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "债券代码",
            "债券简称",
            "公告日期",
            "转股代码",
            "转股简称",
            "转股价格",
            "自愿转换期起始日",
            "自愿转换期终止日",
            "标的股票",
            "债券名称",
        ]
    ]
    temp_df["公告日期"] = pd.to_datetime(temp_df["公告日期"], errors="coerce").dt.date
    temp_df["自愿转换期起始日"] = pd.to_datetime(
        temp_df["自愿转换期起始日"], errors="coerce"
    ).dt.date
    temp_df["自愿转换期终止日"] = pd.to_datetime(
        temp_df["自愿转换期终止日"], errors="coerce"
    ).dt.date
    temp_df["转股价格"] = pd.to_numeric(temp_df["转股价格"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    bond_treasure_issue_cninfo_df = bond_treasure_issue_cninfo(
        start_date="20210910", end_date="20211109"
    )
    print(bond_treasure_issue_cninfo_df)

    bond_local_government_issue_cninfo_df = bond_local_government_issue_cninfo(
        start_date="20210911", end_date="20211110"
    )
    print(bond_local_government_issue_cninfo_df)

    bond_corporate_issue_cninfo_df = bond_corporate_issue_cninfo(
        start_date="20210911", end_date="20211110"
    )
    print(bond_corporate_issue_cninfo_df)

    bond_cov_issue_cninfo_df = bond_cov_issue_cninfo(
        start_date="20210913", end_date="20211112"
    )
    print(bond_cov_issue_cninfo_df)

    bond_cov_stock_issue_cninfo_df = bond_cov_stock_issue_cninfo()
    print(bond_cov_stock_issue_cninfo_df)
