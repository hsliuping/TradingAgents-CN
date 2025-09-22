#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/19 18:30
Desc: 东方财富网-数据中心-特色数据-高管持股
https://data.eastmoney.com/executive/list.html
"""

import pandas as pd
import requests
from tqdm import tqdm


def stock_hold_management_detail_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-高管持股-董监高及相关人员持股变动明细
    https://data.eastmoney.com/executive/list.html
    :return: 董监高及相关人员持股变动明细
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_EXECUTIVE_HOLD_DETAILS",
        "columns": "ALL",
        "quoteColumns": "",
        "filter": "",
        "pageNumber": "1",
        "pageSize": "5000",
        "sortTypes": "-1,1,1",
        "sortColumns": "CHANGE_DATE,SECURITY_CODE,PERSON_NAME",
        "source": "WEB",
        "client": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
                "p": page,
                "pageNo": page,
                "pageNum": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.rename(
        columns={
            "SECURITY_CODE": "代码",
            "DERIVE_SECURITY_CODE": "-",
            "SECURITY_NAME": "名称",
            "CHANGE_DATE": "日期",
            "PERSON_NAME": "变动人",
            "CHANGE_SHARES": "变动股数",
            "AVERAGE_PRICE": "成交均价",
            "CHANGE_AMOUNT": "变动金额",
            "CHANGE_REASON": "变动原因",
            "CHANGE_RATIO": "变动比例",
            "CHANGE_AFTER_HOLDNUM": "变动后持股数",
            "HOLD_TYPE": "持股种类",
            "DSE_PERSON_NAME": "董监高人员姓名",
            "POSITION_NAME": "职务",
            "PERSON_DSE_RELATION": "变动人与董监高的关系",
            "ORG_CODE": "-",
            "GGEID": "-",
            "BEGIN_HOLD_NUM": "开始时持有",
            "END_HOLD_NUM": "结束后持有",
        },
        inplace=True,
    )

    big_df = big_df[
        [
            "日期",
            "代码",
            "名称",
            "变动人",
            "变动股数",
            "成交均价",
            "变动金额",
            "变动原因",
            "变动比例",
            "变动后持股数",
            "持股种类",
            "董监高人员姓名",
            "职务",
            "变动人与董监高的关系",
            "开始时持有",
            "结束后持有",
        ]
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["变动股数"] = pd.to_numeric(big_df["变动股数"], errors="coerce")
    big_df["成交均价"] = pd.to_numeric(big_df["成交均价"], errors="coerce")
    big_df["变动金额"] = pd.to_numeric(big_df["变动金额"], errors="coerce")
    big_df["变动比例"] = pd.to_numeric(big_df["变动比例"], errors="coerce")
    big_df["变动后持股数"] = pd.to_numeric(big_df["变动后持股数"], errors="coerce")
    big_df["开始时持有"] = pd.to_numeric(big_df["开始时持有"], errors="coerce")
    big_df["结束后持有"] = pd.to_numeric(big_df["结束后持有"], errors="coerce")
    return big_df


def stock_hold_management_person_em(
    symbol: str = "001308", name: str = "吴远"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-高管持股-人员增减持股变动明细
    https://data.eastmoney.com/executive/personinfo.html?name=%E5%90%B4%E8%BF%9C&code=001308
    :param symbol: 股票代码
    :type name: str
    :param name: 高管名称
    :type symbol: str
    :return: 人员增减持股变动明细
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_EXECUTIVE_HOLD_DETAILS",
        "columns": "ALL",
        "quoteColumns": "",
        "filter": f'(SECURITY_CODE="{symbol}")(PERSON_NAME="{name}")',
        "pageNumber": "1",
        "pageSize": "5000",
        "sortTypes": "-1,1,1",
        "sortColumns": "CHANGE_DATE,SECURITY_CODE,PERSON_NAME",
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.rename(
        columns={
            "SECURITY_CODE": "代码",
            "DERIVE_SECURITY_CODE": "-",
            "SECURITY_NAME": "名称",
            "CHANGE_DATE": "日期",
            "PERSON_NAME": "变动人",
            "CHANGE_SHARES": "变动股数",
            "AVERAGE_PRICE": "成交均价",
            "CHANGE_AMOUNT": "变动金额",
            "CHANGE_REASON": "变动原因",
            "CHANGE_RATIO": "变动比例",
            "CHANGE_AFTER_HOLDNUM": "变动后持股数",
            "HOLD_TYPE": "持股种类",
            "DSE_PERSON_NAME": "董监高人员姓名",
            "POSITION_NAME": "职务",
            "PERSON_DSE_RELATION": "变动人与董监高的关系",
            "ORG_CODE": "-",
            "GGEID": "-",
            "BEGIN_HOLD_NUM": "开始时持有",
            "END_HOLD_NUM": "结束后持有",
        },
        inplace=True,
    )

    temp_df = temp_df[
        [
            "日期",
            "代码",
            "名称",
            "变动人",
            "变动股数",
            "成交均价",
            "变动金额",
            "变动原因",
            "变动比例",
            "变动后持股数",
            "持股种类",
            "董监高人员姓名",
            "职务",
            "变动人与董监高的关系",
            "开始时持有",
            "结束后持有",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["变动股数"] = pd.to_numeric(temp_df["变动股数"], errors="coerce")
    temp_df["成交均价"] = pd.to_numeric(temp_df["成交均价"], errors="coerce")
    temp_df["变动金额"] = pd.to_numeric(temp_df["变动金额"], errors="coerce")
    temp_df["变动比例"] = pd.to_numeric(temp_df["变动比例"], errors="coerce")
    temp_df["变动后持股数"] = pd.to_numeric(temp_df["变动后持股数"], errors="coerce")
    temp_df["开始时持有"] = pd.to_numeric(temp_df["开始时持有"], errors="coerce")
    temp_df["结束后持有"] = pd.to_numeric(temp_df["结束后持有"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_hold_management_detail_em_df = stock_hold_management_detail_em()
    print(stock_hold_management_detail_em_df)

    stock_hold_management_person_em_df = stock_hold_management_person_em(
        symbol="001308", name="吴远"
    )
    print(stock_hold_management_person_em_df)
