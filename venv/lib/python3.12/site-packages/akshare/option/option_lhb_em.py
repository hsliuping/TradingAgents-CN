# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/7/30 17:00
Desc: 东方财富网-数据中心-特色数据-期权龙虎榜单
https://data.eastmoney.com/other/qqlhb.html
"""

import pandas as pd
import requests


def option_lhb_em(
    symbol: str = "510050",
    indicator: str = "期权交易情况-认沽交易量",
    trade_date: str = "20220121",
) -> pd.DataFrame:
    """
    东方财富网-数据中心-期货期权-期权龙虎榜单
    https://data.eastmoney.com/other/qqlhb.html
    :param symbol: 期权代码; choice of {"510050", "510300", "159919"}
    :type symbol: str
    :param indicator: 需要获取的指标; choice of {"期权交易情况-认沽交易量","期权持仓情况-认沽持仓量", "期权交易情况-认购交易量", "期权持仓情况-认购持仓量"}
    :type indicator: str
    :param trade_date: 交易日期
    :type trade_date: str
    :return: 期权龙虎榜单
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/get"
    params = {
        "type": "RPT_IF_BILLBOARD_TD",
        "sty": "ALL",
        "filter": f"""(SECURITY_CODE="{symbol}")(TRADE_DATE='{'-'.join([trade_date[:4],
                                                                        trade_date[4:6], trade_date[6:]])}')""",
        "p": "1",
        "pss": "200",
        "source": "IFBILLBOARD",
        "client": "WEB",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    if indicator == "期权交易情况-认沽交易量":
        temp_df = temp_df.iloc[:7, :]
        temp_df.columns = [
            "交易类型",
            "交易日期",
            "证券代码",
            "标的名称",
            "-",
            "-",
            "机构",
            "名次",
            "交易量",
            "增减",
            "净认沽量",
            "占总交易量比例",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
        ]
        temp_df = temp_df[
            [
                "交易类型",
                "交易日期",
                "证券代码",
                "标的名称",
                "名次",
                "机构",
                "交易量",
                "增减",
                "净认沽量",
                "占总交易量比例",
            ]
        ]
        temp_df["交易日期"] = pd.to_datetime(
            temp_df["交易日期"], errors="coerce"
        ).dt.date
        temp_df["名次"] = pd.to_numeric(temp_df["名次"], errors="coerce")
        temp_df["交易量"] = pd.to_numeric(temp_df["交易量"], errors="coerce")
        temp_df["增减"] = pd.to_numeric(temp_df["增减"], errors="coerce")
        temp_df["净认沽量"] = pd.to_numeric(temp_df["净认沽量"], errors="coerce")
        temp_df["占总交易量比例"] = pd.to_numeric(
            temp_df["占总交易量比例"], errors="coerce"
        )
        temp_df.reset_index(drop=True, inplace=True)
        return temp_df
    elif indicator == "期权持仓情况-认沽持仓量":
        temp_df = temp_df.iloc[7:14, :]
        temp_df.columns = [
            "交易类型",
            "交易日期",
            "证券代码",
            "标的名称",
            "-",
            "-",
            "机构",
            "名次",
            "-",
            "-",
            "-",
            "-",
            "-",
            "持仓量",
            "增减",
            "净持仓量",
            "占总交易量比例",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
        ]
        temp_df = temp_df[
            [
                "交易类型",
                "交易日期",
                "证券代码",
                "标的名称",
                "名次",
                "机构",
                "持仓量",
                "增减",
                "净持仓量",
                "占总交易量比例",
            ]
        ]
        temp_df["交易日期"] = pd.to_datetime(
            temp_df["交易日期"], errors="coerce"
        ).dt.date
        temp_df["名次"] = pd.to_numeric(temp_df["名次"], errors="coerce")
        temp_df["持仓量"] = pd.to_numeric(temp_df["持仓量"], errors="coerce")
        temp_df["增减"] = pd.to_numeric(temp_df["增减"], errors="coerce")
        temp_df["净持仓量"] = pd.to_numeric(temp_df["净持仓量"], errors="coerce")
        temp_df["占总交易量比例"] = pd.to_numeric(
            temp_df["占总交易量比例"], errors="coerce"
        )
        temp_df.reset_index(drop=True, inplace=True)
        return temp_df
    elif indicator == "期权交易情况-认购交易量":
        temp_df = temp_df.iloc[14:21, :]
        temp_df.columns = [
            "交易类型",
            "交易日期",
            "证券代码",
            "标的名称",
            "-",
            "-",
            "机构",
            "名次",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "交易量",
            "增减",
            "净交易量",
            "占总交易量比例",
            "-",
            "-",
            "-",
            "-",
        ]
        temp_df = temp_df[
            [
                "交易类型",
                "交易日期",
                "证券代码",
                "标的名称",
                "名次",
                "机构",
                "交易量",
                "增减",
                "净交易量",
                "占总交易量比例",
            ]
        ]
        temp_df["交易日期"] = pd.to_datetime(
            temp_df["交易日期"], errors="coerce"
        ).dt.date
        temp_df["名次"] = pd.to_numeric(temp_df["名次"], errors="coerce")
        temp_df["交易量"] = pd.to_numeric(temp_df["交易量"], errors="coerce")
        temp_df["增减"] = pd.to_numeric(temp_df["增减"], errors="coerce")
        temp_df["净交易量"] = pd.to_numeric(temp_df["净交易量"], errors="coerce")
        temp_df["占总交易量比例"] = pd.to_numeric(
            temp_df["占总交易量比例"], errors="coerce"
        )
        temp_df.reset_index(drop=True, inplace=True)
        return temp_df
    elif indicator == "期权持仓情况-认购持仓量":
        temp_df = temp_df.iloc[21:, :]
        temp_df.rename(
            columns={
                "MEMBER_RANK": "名次",
                "MEMBER_NAME_ABBR": "机构",
                "BUY_POSITION": "持仓量",
                "BUY_POSITION_CHANGE": "增减",
                "NET_BUY_POSITION": "净持仓量",
                "BUY_POSITION_RATIO": "占总交易量比例",
                "TRADE_TYPE": "交易类型",
                "TRADE_DATE": "交易日期",
                "SECURITY_CODE": "证券代码",
                "TARGET_NAME": "标的名称",
            },
            inplace=True,
        )
        temp_df = temp_df[
            [
                "交易类型",
                "交易日期",
                "证券代码",
                "标的名称",
                "名次",
                "机构",
                "持仓量",
                "增减",
                "净持仓量",
                "占总交易量比例",
            ]
        ]
        temp_df["交易日期"] = pd.to_datetime(
            temp_df["交易日期"], errors="coerce"
        ).dt.date
        temp_df["名次"] = pd.to_numeric(temp_df["名次"], errors="coerce")
        temp_df["持仓量"] = pd.to_numeric(temp_df["持仓量"], errors="coerce")
        temp_df["增减"] = pd.to_numeric(temp_df["增减"], errors="coerce")
        temp_df["净持仓量"] = pd.to_numeric(temp_df["净持仓量"], errors="coerce")
        temp_df["占总交易量比例"] = pd.to_numeric(
            temp_df["占总交易量比例"], errors="coerce"
        )
        temp_df.reset_index(drop=True, inplace=True)
        return temp_df


if __name__ == "__main__":
    option_lhb_em_df = option_lhb_em(
        symbol="510300", indicator="期权交易情况-认购交易量", trade_date="20220124"
    )
    print(option_lhb_em_df)

    option_lhb_em_df = option_lhb_em(
        symbol="510300", indicator="期权交易情况-认沽交易量", trade_date="20220124"
    )
    print(option_lhb_em_df)

    option_lhb_em_df = option_lhb_em(
        symbol="159919", indicator="期权持仓情况-认购持仓量", trade_date="20240712"
    )
    print(option_lhb_em_df)

    option_lhb_em_df = option_lhb_em(
        symbol="510300", indicator="期权持仓情况-认沽持仓量", trade_date="20220124"
    )
    print(option_lhb_em_df)
