#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/1/4 17:00
Desc: 天天基金-基金档案
https://fundf10.eastmoney.com/jjfl_015641.html
"""

from io import StringIO

import pandas as pd
import requests


def fund_fee_em(symbol: str = "015641", indicator: str = "认购费率") -> pd.DataFrame:
    """
    天天基金-基金档案-购买信息
    https://fundf10.eastmoney.com/jjfl_015641.html
    :param symbol: 基金代码
    :type symbol: str
    :param indicator: choice of {"交易状态", "申购与赎回金额", "交易确认日", "运作费用", "认购费率", "申购费率", "赎回费率"}
    :type indicator: str
    :return: 交易规则
    :rtype: pandas.DataFrame
    """
    url = f"https://fundf10.eastmoney.com/jjfl_{symbol}.html"
    r = requests.get(url)

    if indicator == "交易状态":
        temp_df = pd.read_html(StringIO(r.text))[1]
    elif indicator == "申购与赎回金额":
        temp_df_1 = pd.read_html(StringIO(r.text))[2]
        temp_df_2 = pd.read_html(StringIO(r.text))[3]
        temp_df = pd.concat(objs=[temp_df_1, temp_df_2], ignore_index=True)
    elif indicator == "交易确认日":
        temp_df = pd.read_html(StringIO(r.text))[4]
    elif indicator == "运作费用":
        temp_df = pd.read_html(StringIO(r.text))[5]
    elif indicator == "认购费率":
        temp_df = pd.read_html(StringIO(r.text))[6]
        temp_df["原费率"] = temp_df["原费率|天天基金优惠费率"].str.split(
            "|", expand=True
        )[0]
        temp_df["天天基金优惠费率"] = temp_df["原费率|天天基金优惠费率"].str.split(
            "|", expand=True
        )[1]
        del temp_df["原费率|天天基金优惠费率"]
        temp_df.loc[3, "天天基金优惠费率"] = temp_df.loc[3, "原费率"]
        temp_df["原费率"] = temp_df["原费率"].str.strip()
        temp_df["天天基金优惠费率"] = temp_df["天天基金优惠费率"].str.strip()
    elif indicator == "申购费率":
        temp_df = pd.read_html(StringIO(r.text))[7]
        temp_df["原费率"] = temp_df[
            "原费率|天天基金优惠费率 银行卡购买|活期宝购买"
        ].str.split("|", expand=True)[0]
        temp_df["天天基金优惠费率-银行卡购买"] = temp_df[
            "原费率|天天基金优惠费率 银行卡购买|活期宝购买"
        ].str.split("|", expand=True)[1]
        temp_df["天天基金优惠费率-活期宝购买"] = temp_df[
            "原费率|天天基金优惠费率 银行卡购买|活期宝购买"
        ].str.split("|", expand=True)[2]
        del temp_df["原费率|天天基金优惠费率 银行卡购买|活期宝购买"]
        temp_df.loc[3, "天天基金优惠费率-银行卡购买"] = temp_df.loc[3, "原费率"]
        temp_df.loc[3, "天天基金优惠费率-活期宝购买"] = temp_df.loc[3, "原费率"]
        temp_df["原费率"] = temp_df["原费率"].str.strip()
        temp_df["天天基金优惠费率-银行卡购买"] = temp_df[
            "天天基金优惠费率-银行卡购买"
        ].str.strip()
        temp_df["天天基金优惠费率-活期宝购买"] = temp_df[
            "天天基金优惠费率-活期宝购买"
        ].str.strip()
    elif indicator == "赎回费率":
        temp_df = pd.read_html(StringIO(r.text))[8]
    else:
        temp_df = pd.DataFrame([])
    return temp_df


if __name__ == "__main__":
    fund_fee_em_df = fund_fee_em(symbol="015641", indicator="交易状态")
    print(fund_fee_em_df)

    fund_fee_em_df = fund_fee_em(symbol="015641", indicator="申购与赎回金额")
    print(fund_fee_em_df)

    fund_fee_em_df = fund_fee_em(symbol="015641", indicator="交易确认日")
    print(fund_fee_em_df)

    fund_fee_em_df = fund_fee_em(symbol="015641", indicator="运作费用")
    print(fund_fee_em_df)

    fund_fee_em_df = fund_fee_em(symbol="015641", indicator="认购费率")
    print(fund_fee_em_df)

    fund_fee_em_df = fund_fee_em(symbol="015641", indicator="申购费率")
    print(fund_fee_em_df)

    fund_fee_em_df = fund_fee_em(symbol="015641", indicator="赎回费率")
    print(fund_fee_em_df)
