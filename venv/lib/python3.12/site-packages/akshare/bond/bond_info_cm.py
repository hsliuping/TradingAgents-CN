#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/10 14:00
Desc: 中国外汇交易中心暨全国银行间同业拆借中心
https://www.chinamoney.com.cn/chinese/scsjzqxx/
"""

import functools

import pandas as pd
import requests
from akshare.utils.tqdm import get_tqdm
from akshare.bond.bond_china import bond_china_close_return_map


@functools.lru_cache()
def bond_info_cm_query(symbol: str = "评级等级") -> pd.DataFrame:
    """
    中国外汇交易中心暨全国银行间同业拆借中心-查询相关指标的参数
    https://www.chinamoney.com.cn/chinese/scsjzqxx/
    :param symbol: choice of {"主承销商", "债券类型", "息票类型", "发行年份", "评级等级"}
    :type symbol: str
    :return: 查询相关指标的参数
    :rtype: pandas.DataFrame
    """
    bond_china_close_return_map()
    if symbol == "主承销商":
        url = "https://www.chinamoney.com.cn/ags/ms/cm-u-bond-md/EntyFullNameSearchCondition"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/109.0.0.0 Safari/537.36"
        }
        r = requests.post(url, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["enty"])
        temp_df.columns = ["code", "name"]
        temp_df = temp_df[["name", "code"]]
        return temp_df
    else:
        symbol_map = {
            "债券类型": "bondType",
            "息票类型": "couponType",
            "发行年份": "issueYear",
            "评级等级": "bondRtngShrt",
        }
        url = "https://www.chinamoney.com.cn/ags/ms/cm-u-bond-md/BondBaseInfoSearchCondition"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/109.0.0.0 Safari/537.36"
        }
        r = requests.post(url, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"][f"{symbol_map[symbol]}"])
        if temp_df.shape[1] == 1:
            temp_df.columns = ["name"]
            temp_df["code"] = temp_df["name"]
        temp_df.columns = ["code", "name"]
        temp_df = temp_df[["name", "code"]]
        return temp_df


@functools.lru_cache()
def bond_info_cm(
    bond_name: str = "",
    bond_code: str = "",
    bond_issue: str = "",
    bond_type: str = "",
    coupon_type: str = "",
    issue_year: str = "",
    underwriter: str = "",
    grade: str = "",
) -> pd.DataFrame:
    """
    中国外汇交易中心暨全国银行间同业拆借中心-数据-债券信息-信息查询
    https://www.chinamoney.com.cn/chinese/scsjzqxx/
    :param bond_name: 债券名称
    :type bond_name: str
    :param bond_code: 债券代码
    :type bond_code: str
    :param bond_issue: 发行人/受托机构
    :type bond_issue: str
    :param bond_type: 债券类型
    :type bond_type: str
    :param coupon_type: 息票类型
    :type coupon_type: str
    :param issue_year: 发行年份
    :type issue_year: str
    :param underwriter: 主承销商
    :type underwriter: str
    :param grade: 评级等级
    :type grade: str
    :return: 信息查询结果
    :rtype: pandas.DataFrame
    """
    bond_china_close_return_map()
    if bond_type:
        bond_type_df = bond_info_cm_query(symbol="债券类型")
        bond_type_df_value = bond_type_df[bond_type_df["name"] == bond_type][
            "code"
        ].values[0]
    else:
        bond_type_df_value = ""

    if coupon_type:
        coupon_type_df = bond_info_cm_query(symbol="息票类型")
        coupon_type_df_value = coupon_type_df[coupon_type_df["name"] == coupon_type][
            "code"
        ].values[0]
    else:
        coupon_type_df_value = ""

    if underwriter:
        underwriter_df = bond_info_cm_query(symbol="主承销商")
        underwriter_value = underwriter_df[underwriter_df["name"] == underwriter][
            "code"
        ].values[0]
    else:
        underwriter_value = ""

    url = "https://www.chinamoney.com.cn/ags/ms/cm-u-bond-md/BondMarketInfoList2"
    payload = {
        "pageNo": "1",
        "pageSize": "15",
        "bondName": bond_name,
        "bondCode": bond_code,
        "issueEnty": bond_issue,
        "bondType": bond_type_df_value if bond_type_df_value else "",
        "bondSpclPrjctVrty": "",
        "couponType": coupon_type_df_value if coupon_type_df_value else "",
        "issueYear": issue_year,
        "entyDefinedCode": underwriter_value if underwriter_value else "",
        "rtngShrt": grade,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/109.0.0.0 Safari/537.36"
    }
    r = requests.post(url, data=payload, headers=headers)
    data_json = r.json()
    total_page = data_json["data"]["pageTotal"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        payload.update({"pageNo": page})
        r = requests.post(url, data=payload, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["resultList"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.rename(
        columns={
            "bondDefinedCode": "查询代码",
            "bondName": "债券简称",
            "bondCode": "债券代码",
            "issueStartDate": "发行日期",
            "issueEndDate": "-",
            "bondTypeCode": "-",
            "bondType": "债券类型",
            "entyFullName": "发行人/受托机构",
            "entyDefinedCode": "-",
            "debtRtng": "最新债项评级",
            "isin": "-",
            "inptTp": "-",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "债券简称",
            "债券代码",
            "发行人/受托机构",
            "债券类型",
            "发行日期",
            "最新债项评级",
            "查询代码",
        ]
    ]
    return big_df


@functools.lru_cache()
def bond_info_detail_cm(symbol: str = "淮安农商行CDSD2022021012") -> pd.DataFrame:
    """
    中国外汇交易中心暨全国银行间同业拆借中心-数据-债券信息-信息查询-债券详情
    https://www.chinamoney.com.cn/chinese/zqjc/?bondDefinedCode=egfjh08154
    :param symbol: 债券简称
    :type symbol: str
    :return: 债券详情
    :rtype: pandas.DataFrame
    """
    bond_china_close_return_map()
    url = "https://www.chinamoney.com.cn/ags/ms/cm-u-bond-md/BondDetailInfo"
    inner_bond_info_cm_df = bond_info_cm(bond_name=symbol)
    bond_code = inner_bond_info_cm_df["查询代码"].values[0]
    payload = {"bondDefinedCode": bond_code}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/109.0.0.0 Safari/537.36"
    }
    r = requests.post(url, data=payload, headers=headers)
    data_json = r.json()
    data_dict = data_json["data"]["bondBaseInfo"]
    if data_dict["creditRateEntyList"]:
        del data_dict["creditRateEntyList"]
    if data_dict["exerciseInfoList"]:
        del data_dict["exerciseInfoList"]
    temp_df = pd.DataFrame.from_dict(data_dict, orient="index")
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["name", "value"]
    return temp_df


if __name__ == "__main__":
    bond_info_cm_df = bond_info_cm(
        bond_name="",
        bond_code="",
        bond_issue="",
        bond_type="短期融资券",
        coupon_type="零息式",
        issue_year="2019",
        grade="A-1",
        underwriter="重庆农村商业银行股份有限公司",
    )
    print(bond_info_cm_df)

    bond_info_detail_cm_df = bond_info_detail_cm(symbol="19万林投资CP001")
    print(bond_info_detail_cm_df)
