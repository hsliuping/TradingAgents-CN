#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/5/11 16:00
Desc: 东方财富-港股-公司概况
https://emweb.securities.eastmoney.com/PC_HKF10/pages/home/index.html?code=03900&type=web&color=w#/CompanyProfile
"""

import pandas as pd
import requests


def stock_hk_security_profile_em(symbol: str = "03900") -> pd.DataFrame:
    """
    东方财富-港股-证券资料
    https://emweb.securities.eastmoney.com/PC_HKF10/pages/home/index.html?code=03900&type=web&color=w#/CompanyProfile
    :param symbol: 股票代码
    :type symbol: str
    :return: 证券资料
    :rtype: pandas.DataFrame
    """
    url = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'
    params = {
        'reportName': 'RPT_HKF10_INFO_SECURITYINFO',
        'columns': 'SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,SECURITY_TYPE,LISTING_DATE,ISIN_CODE,BOARD,'
                   'TRADE_UNIT,TRADE_MARKET,GANGGUTONGBIAODISHEN,GANGGUTONGBIAODIHU,PAR_VALUE,'
                   'ISSUE_PRICE,ISSUE_NUM,YEAR_SETTLE_DAY',
        'quoteColumns': '',
        'filter': f'(SECUCODE="{symbol}.HK")',
        'pageNumber': '1',
        'pageSize': '200',
        'sortTypes': '',
        'sortColumns': '',
        'source': 'F10',
        'client': 'PC',
        'v': '04748497219912483'
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json['result']['data'])
    field_mapping = {
        "BOARD": "板块",
        "GANGGUTONGBIAODIHU": "是否沪港通标的",
        "GANGGUTONGBIAODISHEN": "是否深港通标的",
        "ISIN_CODE": "ISIN（国际证券识别编码）",
        "ISSUE_NUM": "发行量(股)",
        "ISSUE_PRICE": "发行价",
        "LISTING_DATE": "上市日期",
        "PAR_VALUE": "每股面值",
        "SECUCODE": "证券代码",
        "SECURITY_NAME_ABBR": "证券简称",
        "SECURITY_TYPE": "证券类型",
        "TRADE_MARKET": "交易所",
        "TRADE_UNIT": "每手股数",
        "YEAR_SETTLE_DAY": "年结日"
    }
    temp_df.rename(columns=field_mapping, inplace=True)
    temp_df = temp_df[[
        "证券代码",
        "证券简称",
        "上市日期",
        "证券类型",
        "发行价",
        "发行量(股)",
        "每手股数",
        "每股面值",
        "交易所",
        "板块",
        "年结日",
        "ISIN（国际证券识别编码）",
        "是否沪港通标的",
        "是否深港通标的",
    ]]
    return temp_df


def stock_hk_company_profile_em(symbol: str = "03900") -> pd.DataFrame:
    """
    东方财富-港股-公司资料
    https://emweb.securities.eastmoney.com/PC_HKF10/pages/home/index.html?code=03900&type=web&color=w#/CompanyProfile
    :param symbol: 股票代码
    :type symbol: str
    :return: 公司资料
    :rtype: pandas.DataFrame
    """
    url = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'
    params = {
        'reportName': 'RPT_HKF10_INFO_ORGPROFILE',
        'columns': 'SECUCODE,SECURITY_CODE,ORG_NAME,ORG_EN_ABBR,BELONG_INDUSTRY,FOUND_DATE,CHAIRMAN,'
                   'SECRETARY,ACCOUNT_FIRM,REG_ADDRESS,ADDRESS,YEAR_SETTLE_DAY,EMP_NUM,ORG_TEL,ORG_FAX,ORG_EMAIL,'
                   'ORG_WEB,ORG_PROFILE,REG_PLACE',
        'quoteColumns': '',
        'filter': f'(SECUCODE="{symbol}.HK")',
        'pageNumber': '1',
        'pageSize': '200',
        'sortTypes': '',
        'sortColumns': '',
        'source': 'F10',
        'client': 'PC',
        'v': '04748497219912483'
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json['result']['data'])
    field_mapping = {
        'ACCOUNT_FIRM': '核数师',
        'ADDRESS': '办公地址',
        'BELONG_INDUSTRY': '所属行业',
        'CHAIRMAN': '董事长',
        'EMP_NUM': '员工人数',
        'FOUND_DATE': '公司成立日期',
        'ORG_EMAIL': 'E-MAIL',
        'ORG_EN_ABBR': '英文名称',
        'ORG_FAX': '传真',
        'ORG_NAME': '公司名称',
        'ORG_PROFILE': '公司介绍',
        'ORG_TEL': '联系电话',
        'ORG_WEB': '公司网址',
        'REG_ADDRESS': '注册地址',
        'REG_PLACE': '注册地',
        'SECRETARY': '公司秘书',
        'SECUCODE': '股票代码',
        'SECURITY_CODE': '证券代码',
        'YEAR_SETTLE_DAY': '年结日'
    }
    temp_df.rename(columns=field_mapping, inplace=True)
    temp_df = temp_df[[
        "公司名称",
        "英文名称",
        "注册地",
        "注册地址",
        "公司成立日期",
        "所属行业",
        "董事长",
        "公司秘书",
        "员工人数",
        "办公地址",
        "公司网址",
        "E-MAIL",
        "年结日",
        "联系电话",
        "核数师",
        "传真",
        "公司介绍",
    ]]
    return temp_df


if __name__ == "__main__":
    stock_hk_security_profile_em_df = stock_hk_security_profile_em(symbol="03900")
    print(stock_hk_security_profile_em_df)

    stock_hk_company_profile_em_df = stock_hk_company_profile_em(symbol="03900")
    print(stock_hk_company_profile_em_df)
