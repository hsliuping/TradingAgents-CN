#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/4/3 18:00
Desc: 东方财富-A股数据-股本结构
https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SH603392&color=b#/gbjg/gbjg
"""

import requests
import pandas as pd


def stock_zh_a_gbjg_em(symbol: str = "603392.SH") -> pd.DataFrame:
    """
    东方财富-A股数据-股本结构
    https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html#/gbjg
    :param symbol: 股票代码
    :type symbol: str
    :return: 股本结构
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    params = {
        "reportName": "RPT_F10_EH_EQUITY",
        "columns": "SECUCODE,SECURITY_CODE,END_DATE,TOTAL_SHARES,LIMITED_SHARES,LIMITED_OTHARS,"
                   "LIMITED_DOMESTIC_NATURAL,LIMITED_STATE_LEGAL,LIMITED_OVERSEAS_NOSTATE,LIMITED_OVERSEAS_NATURAL,"
                   "UNLIMITED_SHARES,LISTED_A_SHARES,B_FREE_SHARE,H_FREE_SHARE,FREE_SHARES,LIMITED_A_SHARES,"
                   "NON_FREE_SHARES,LIMITED_B_SHARES,OTHER_FREE_SHARES,LIMITED_STATE_SHARES,"
                   "LIMITED_DOMESTIC_NOSTATE,LOCK_SHARES,LIMITED_FOREIGN_SHARES,LIMITED_H_SHARES,"
                   "SPONSOR_SHARES,STATE_SPONSOR_SHARES,SPONSOR_SOCIAL_SHARES,RAISE_SHARES,"
                   "RAISE_STATE_SHARES,RAISE_DOMESTIC_SHARES,RAISE_OVERSEAS_SHARES,CHANGE_REASON",
        "quoteColumns": "",
        "filter": f'(SECUCODE="{symbol}")',
        "pageNumber": "1",
        "pageSize": "20",
        "sortTypes": "-1",
        "sortColumns": "END_DATE",
        "source": "HSF10",
        "client": "PC",
        "v": "047483522105257925"
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json['result']['data'])
    temp_df.rename(columns={
        "END_DATE": "变更日期",
        "TOTAL_SHARES": "总股本",
        "LISTED_A_SHARES": "已上市流通A股",
        "FREE_SHARES": "已流通股份",
        "CHANGE_REASON": "变动原因",
        "LIMITED_A_SHARES": "流通受限股份",
        "LIMITED_OTHARS": "其他内资持股(受限)",
        "LIMITED_DOMESTIC_NOSTATE": "境内法人持股(受限)",
        "LIMITED_DOMESTIC_NATURAL": "境内自然人持股(受限)",
    }, inplace=True)
    temp_df = temp_df[[
        "变更日期",
        "总股本",
        "流通受限股份",
        "其他内资持股(受限)",
        "境内法人持股(受限)",
        "境内自然人持股(受限)",
        "已流通股份",
        "已上市流通A股",
        "变动原因",
    ]]
    temp_df["变更日期"] = pd.to_datetime(temp_df["变更日期"], errors="coerce").dt.date
    temp_df["总股本"] = pd.to_numeric(temp_df["总股本"], errors="coerce")
    temp_df["流通受限股份"] = pd.to_numeric(temp_df["流通受限股份"], errors="coerce")
    temp_df["其他内资持股(受限)"] = pd.to_numeric(temp_df["其他内资持股(受限)"], errors="coerce")
    temp_df["境内法人持股(受限)"] = pd.to_numeric(temp_df["境内法人持股(受限)"], errors="coerce")
    temp_df["境内自然人持股(受限)"] = pd.to_numeric(temp_df["境内自然人持股(受限)"], errors="coerce")
    temp_df["已流通股份"] = pd.to_numeric(temp_df["已流通股份"], errors="coerce")
    temp_df["已上市流通A股"] = pd.to_numeric(temp_df["已上市流通A股"], errors="coerce")
    return temp_df


if __name__ == '__main__':
    stock_zh_a_gbjg_em_df = stock_zh_a_gbjg_em(symbol="603392.SH")
    print(stock_zh_a_gbjg_em_df)
